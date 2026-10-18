# Packet58g full-shape submit audit

The historical cache-setup audit below was insufficient: it did not reach
`prepare_commands`. The new [full-shape gate](evidence/fullshape-submit-cpu.json)
runs actual initialization, all 1,486 dispatch sites and both context extents.
Its 3,446 rows total 24,287,732,980 device bytes and 48,633,091,712 host-pinned
bytes. Device bytes exactly match 58f's failed load log. mmap reserves real,
distinct logical extents; only 29,356,032 bytes peak RSS were observed.

The failing argument is the layer-2 gate's 8,192-byte pointer table, not its
360,448,000-byte host bank. The up table has the same mismatch. The repair
changes how p28 reads these tables; no allocation or memory budget changes.
[Old refusal](evidence/fullshape-58f-refusal.txt), [census](evidence/fullshape-census.json),
[prepared argument ledger](evidence/fullshape-prepared-arguments-parity0.jsonl).

# Packet58d allocation audit

Scope: packet58c KD, physical card 0, one rank, context 4096, BF16 KV,
plain decode, resident target, zero-copy misses, empty 18,000,000,000-byte LRU
expert cache. Arithmetic remains `iq3-p49-split32-v1`.

The first bad request is **`card0:cache-table-staging`** at 58c main.cpp:852.
The second, not reached in that failed run, is **`card0:cache-route-readback`**
at main.cpp:856. Both use `pinned_slab/process`; `planned(pinned_slab)` is
`transfer`. Both now request `transfer`. The owner plan and enforcement are
unchanged. These reusable staging slabs remain owned until drained teardown;
the lifetime tag does not trigger an automatic free after each copy. Table
publication and route readback already wait before reusing their storage.

## Actual order

`Engine::initialize` allocates workspace, KV and request state **before**
loading weights. The output head is in the weight-loading pass, also before
`initialize_cache`. The last upload reported by 58c is `output_hc_norm.weight`.
After that upload, these are the complete arena allocation requests, in order:

| Label | Bytes | Memory | Category | Requested in 58c | Plan / 58d |
| --- | ---: | --- | --- | --- | --- |
| immutable-expert-cache | 18,000,000,000 | device | weights | process | process |
| cache-table-staging | 1,179,648 | pinned | pinned-copy-slab | **process (wrong)** | transfer |
| cache-route-readback | 5,760 | pinned | pinned-copy-slab | **process (wrong)** | transfer |

Between the first two requests, the engine creates CPU LRU metadata for
48 × 512 experts. After staging allocation it publishes all 144 pointer tables,
drains those copies, collects 48 route sources, then allocates route readback.
`prepare_plan` creates CPU launch descriptors, not arena allocations. In this
resident cache path its weight lookups find the already-loaded handles.

## All engine allocation call sites

Line numbers refer to frozen packet58c `main.cpp`; 58d keeps these positions.
All pairs below agree with `owner.cpp:planned` except the two listed above.

| Call site / labels | Category and lifetime | When reached |
| --- | --- | --- |
| 765–770, Engine allocation wrapper | Forwards caller pair to real Arena check | Every engine allocation |
| 826, pinned-experts:* | weights / process, pinned memory | Weight loading, 144 banks |
| 833, expert-table:* | weights / process | Weight loading, 144 tables |
| 847, immutable-expert-cache | weights / process | Post-load |
| 852, cache-table-staging | pinned-slab / transfer after repair | Post-load |
| 856, cache-route-readback | pinned-slab / transfer after repair | Post-load |
| 899, weight:* including output head/norm | weights / process | Weight loading |
| 966–976, parallel-controls, attention-scores, attention-probabilities, layer-snapshots, prepared-fp32-input, gemv-workspace, compact-routes, ordered-mixture, mixture-one | scratch / transaction | Before weight loading |
| 977, bounded-copy | pinned-slab / transfer | Before weight loading |
| 980, rope-v2 | weights / process | Before weight loading |
| 982, operator-scratch | scratch / transaction | Before weight loading |
| 1012, planned .state, *history, token_history | recurrent / request | Before weight loading |
| 1012, planned .keys, .values, .pooled, .raw | KV / request | Before weight loading |
| 1012, all other planned buffers, including final/logit buffers | scratch / transaction | Before weight loading |
| 1116, selected:* | weights / process | Non-cache expert path; bypassed by KD's cache path |

`rank.hpp:72` uses recurrent/request for alternate state banks and is outside
this rank-local plain-decode setup.

`mtp.hpp` is outside this plain-decode configuration. Its general allocator
maps weights/process, KV/request, and scratch/transaction; publication uses
output-ring/request and half-staging uses pinned-slab/transfer. No mismatched
pair appears there. Fixture allocators use scratch/transaction or deliberately
invalid pairs for negative tests; they are not KD allocation paths. Native
backend `allocate(bytes, memory)` implementations receive no category or
lifetime and cannot bypass the engine's arena check.

## Regression coverage

The CPU-only entry in `postload_allocation_test.hpp` constructs the production
plan from the same metadata TSV, dispatch and selection as KD. It supplies all
144 loaded bank handles and 48 route sources, then calls the **actual
`Engine::initialize_cache`**. Every logical byte extent goes through the real
`Engine::allocate` and `Arena::allocate`. A mock supplies aligned, bounded host
backing; large expert/cache payloads are opaque addresses and copies complete
without moving payloads. It opens no model and contacts no device.

The test checks all three post-load requests, 144 table publications, 48 route
sources, empty LRU state, slab sizes, clean drained teardown and both original
bad requests failing before the backend is called. Negative diagnostics must
contain the exact label, category, requested lifetime and planned lifetime.
This is allocation/setup coverage, not model correctness or device-fit proof.

`postload_allocation_gate.py` pins the CPU binary, its source closure, metadata,
selection, dispatch and retained census/teardown. `seal.py` requires that gate;
`window.build_gate` requires its presence; `queue_runner.py --plan` now checks
the seal before printing commands. Missing-gate planning is covered by a CPU
test. The new seal requires K1a and K1b again; old device receipts cannot be
imported under the existing prerequisite rules.
