# Packet58ac — changed-entry cache publication

2026-10-18. **Decision: no build brief. The required 60% net removal is not
supported by the CPU evidence.** Sparse publication is representable without
changing the arithmetic, but the measured table-packing work is only
**0.053–0.060 ms/publication**, versus **0.738753 ms/token** required. The
remaining device transfer, scatter and synchronization costs are not separately
measured on this identity. Removing most bytes does not establish removal of
most time. This is a feasibility rejection, not proof that a faster publication
implementation is impossible.

The design, CPU equivalence checks and reopening conditions are retained here;
there is no runtime patch, device build, queue proposal or readiness marker.
[Numbers and input hashes](analysis.json), [CPU probe results](host-probe.json),
[do-not-repeat entry](DO-NOT-REPEAT.md),
[work note](../../../../notes/2026-10-18-own-runtime-packet58ac.md).

## Identity and measurement scope

Anchor: packet58z WS128, one B70, **29.259764156562692 tok/s**, Unsloth
UD-IQ3_XXS quantized compressed target, unchanged `iq3-p49-split32-v1`, tile16,
overlapped cache maintenance, 21,552,729,600-byte expert cache, pinned-host
zero-copy misses, context 4096 and full BF16 KV. No draft. The record remains
the owner-authorized 128-token scope; strict512 is false. This work adds no
model-output or device-determinism qualification and changes no speed record.

The replay joins the 2,386 saved cache positions with each prompt's prefill and
generation timings, then selects **events 2–100: 1,188 intervals across twelve
prompts**. It verifies summary/cache hashes against the window receipt and
reconstructs the median of six class medians to within 1e-8 tok/s. It neither
uses prefill as decode evidence nor excludes the first prompt. Per-prompt
publication sensitivities reproduce packet147's +2.210232% at 60% recovery.

Sources:

- [58z WS128 summary](../packet58z-onecard-record/evidence/card0-58z-a/WS128/summary.json),
  [window](../packet58z-onecard-record/evidence/card0-58z-a/WS128/window.json),
  [cache counters](../packet58z-onecard-record/evidence/card0-58z-a/WS128/run/run/cache.jsonl).
- [58z archived 58x source](../packet58z-onecard-record/lineage/58x-build-source.tar.gz),
  SHA256 `efd357edc751e929553880b2638cada3fedb869d2f8584c51ce9bc2646d3ab9f`.
  The replay verifies extracted `build/native/main.cpp`, `native/cache_table.hpp`,
  `native/cache_protocol.hpp`, `native/publish.hpp` and `async_source.py`
  against the archive's build receipt. It reads archive members without
  restoring or changing the frozen tree.
- [58v publication](../packet58v-async-cache/native/publish.hpp),
  [protocol](../packet58v-async-cache/native/cache_protocol.hpp),
  [owner/backend transformation](../packet58v-async-cache/async_source.py),
  [boundaries](../packet58v-async-cache/DO-NOT-REPEAT.md).
- [58y diagnostic](../packet58y-onecard-attribution/analysis/report.json) and
  [instrumentation](../packet58y-onecard-attribution/attribution_source.py).
  Its pre-existing dirty report is read as observed evidence; the replay also
  verifies its raw attribution-file hashes and independently reproduces the
  publication-wait mean. It is an **18 GB, instrumented identity**, not 58z.
- [58j pointer resolver](../packet58j-onecard-port/p58_pointer.hpp), retained
  through the archived source lineage; [packet147 section 2](../packet147-lever-synthesis/PLAN.md#2-current-one-card-receipts-expose-a-smaller-distinct-cache-boundary).

## What is actually published

There are 48 layers × 512 experts = **24,576 logical entries**. CPU `Entry`
contains gate/up/down addresses and a generation, four uint64 words (32 bytes).
The device has **144 separate banks** (48 × three projections); each bank
holds 512 `Pointer` pairs of address and generation (16 bytes).

| Operation | Per publication | Per measured token |
| --- | ---: | ---: |
| CPU packing visits | 73,728 projection entries | 73,728 |
| Unique CPU entry-table storage | 786,432 bytes | Same table, scanned by projection |
| Pinned staging stores | 1,179,648 bytes | 1,179,648 bytes |
| Foreground H2D memcpy | 1 × 1,179,648 bytes | Exactly 1 in all 1,188 intervals |
| Device scatter | 147,456 uint64 stores | 1 launch |
| Scatter logical read + write traffic | 2,359,296 bytes | 2,359,296 bytes |
| Engine terminal-event wait | 1 | 1 |
| Foreground synchronization wrapper during retirement | 1 | 1; wrapper waits copy queue and compute queue |

These are logical bytes, not measured PCIe transactions, memory-controller
traffic or hardware event durations. Source address/generation values supply
1,179,648 bytes of useful CPU loads; actual cache-line traffic can differ.
The publication's memcpy is inside a compute operation, so ordinary
`CopyEngine` H2D counters are not the publication census.

58v already replaced 144 uploads with **one memcpy plus one scatter** in overlap
mode. That saving cannot be claimed again. `publish_cache_table()` starts its
clock before packing, resolves the 144 destination handles, builds a 145-handle
binding list, submits the operation, drains its terminal event, retires events,
and stops its clock. The measured mean is **1.231254209 ms/token**. It includes
CPU preparation, runtime/driver submission, H2D, scatter and completion/retirement.

The saved post-position states show:

| Transition | Charged tokens | Publication ms/token | New fills/token in that group |
| --- | ---: | ---: | ---: |
| Planned → filling: revoke, then launch fills | 592 | 1.234870 | 31.756757; maximum 241 |
| Filling → planned: commit, then plan during compute | 596 | 1.227663 | 0 |

Across all metric intervals there are **15.824916 fills/token**,
**31,369,352.189 fill bytes/token**, hence **47.474747 background projection
copies/token** (three per fill). Those expert-weight copies are outside the
publication timer and remain necessary. Fill counts are delayed admissions,
not current-token misses or an exact dirty-entry census. The receipts do not
record victim IDs or evictions; do not infer the precise sparse-payload size
from fills alone. A 64-entry payload below is a sensitivity, not a measured
mean or a buffer limit.

`Protocol::revoked()` also copies the 786,432-byte CPU plan table before
`publish_cache_table()` starts. Planning makes other full metadata copies
while compute is in flight. Neither cost is silently credited against this
1.231254 ms budget. Initial/capacity-transition full publications are outside
the selected intervals and remain full publications in the design.

## Two-phase ownership and generation rules

1. Position t completes and its routes are owned by the host. After t+1's
   kernels are enqueued, `Cache::prepare()` plans from those routes. Only
   unpublished CPU metadata changes; the old published table and cache bytes
   remain usable by t+1. Every position still updates LRU recency.
2. Once t+1 and its readbacks have drained, `maintenance.running` is false.
   Publish the **revoked** table: every evicted expert gets its pinned-host
   addresses; every fill ID also gets host addresses, with the final plan's
   generation. Wait for publication before allowing any slot overwrite.
3. Launch the three projection fills for each expert onto the separate in-order
   maintenance queue. Its last real event is the ticket. The next position
   reads unchanged residents or immutable pinned-host bytes while fills write
   only revoked slots. There is one outstanding transaction.
4. At a later drained boundary, query the ticket once. An incomplete event
   leaves the safe table intact; there is no hot-path fill wait/retry loop.
   After completion, publish the final plan table, drain it, then commit the
   CPU metadata. A new plan may be prepared during that position's compute.

`Pointer::resolve()` loads the address; **it does not compare the generation**.
Generations are retained in state/receipts; they do not make a racing pointer
write or overwritten slot safe. Each eviction/admission increments generation
using checked addition. Copy the final value exactly, including host-address
entries whose only change is generation. Address and generation writes need
not be atomic only because no reader can overlap publication.

Keep the real fill ticket and owned-plan/state checks. In overlap mode,
`Cache::begin_position()` is bypassed, so `Plan::epoch` alone is not a unique
transaction identifier. Do not design stale-delta rejection around that
assumption. On failed/partial fill or publication, stop new work, retain
resources, drain through the existing failure path, and close failed; restoring
old victim pointers could point into overwritten data. Quiescent switches and
shutdown retain `finish_fills()`. Pinned sources, cache arena, all table handles
and both staging buffers outlive every consuming event.

## Exact sparse design retained for a future brief

**Preferred representation:** a 40-byte record: uint32 expert ID, uint32 zero
reserved field, three uint64 addresses and uint64 generation. One H2D delta
upload followed by one device apply operation writes three `Pointer` pairs per
ID into the existing bank allocations. Destination lookup is built once from
the actual `(layer, projection)` map; never assume its lexicographic iteration
order is `3*layer+projection`.

Record dirty IDs at the two existing mutations in `Cache::prepare`: eviction
and admission. Deduplicate with bounded storage, retain the final plan entry,
and do not scan all 24,576 entries to discover changes. An expert can appear
more than once, including eviction after an earlier fill in the same plan.
Do not increment generations in the publisher. No route policy, fill order,
cache size or numerical operation changes.

- **Revocation:** dirty IDs are the union of victims and fill IDs. Construct
  the exact values of the existing revoked table, including generation-only
  changes. Apply while foreground readers are drained; publication's terminal
  event must complete before the first background fill can start.
- **Completion:** after the real terminal fill event completes, publish the
  final entries for unique fill IDs. Victim-only IDs already have their final
  host pointers. If an ID was later evicted within the plan, publish its final
  host entry, never a pointer derived from the earlier fill's offset. Then
  drain and commit exactly as before.
- **Late fills:** no update. **Empty/no-op transaction:** skip only after
  proving the currently published table is identical; preserve state/commit
  transitions. No empty revocation batches occurred in the 592 measured
  fill-launch positions, so this study credits no empty-batch speed benefit.
- **Bounds and fallback:** validate count, IDs, reserved fields and uniqueness
  before submission; no partial host apply followed by rejection. Inability
  to track a complete dirty set chooses the existing full publication at the
  same safe phase. Invalid state/foreign ticket fails closed. Initialization
  and any existing table reset use full publication.

Worst case: 24,576 × 40 = **983,040 bytes**, fitting both existing
1,179,648-byte staging allocations. Device table handles and their allocation
generations remain unchanged. No extra expert/weight or device staging
allocation is required; a bounded host ID list/marks and destination map need
separate metadata accounting in any later build. Never reuse the pinned upload
buffer while its memcpy is in flight. A full/delta tag selects the correct
operation so a full table cannot be decoded as records.

The device apply must depend on its upload, and the existing owner must retain
the apply event. The current event/foreground drain and no-live-reader rule
remain. This prevents any kernel from reading a slot being written even if
fills complete mid-position. Full `iq3-p49-split32-v1` model output equality
still needs the unchanged packet49 oracle and fresh-process device checks in
a separately authorized implementation; CPU state equivalence is not that gate.

**Alternative:** batched sparse memcpys into each bank under the same phases.
Without a real single batched submission, 64 changed experts imply up to 192
tiny copies instead of one upload/one apply. Contiguous coalescing depends on
actual IDs and cannot be assumed from a fill count. There is no CPU timing
case for selecting this alternative; retain device apply as the design only.

## CPU measurements and the unresolved time split

[host_probe.cpp](host_probe.cpp) compiles only standard C++ and extracted cache
metadata headers. It never links the runtime, SYCL or device libraries.
The actual packing loop is extracted from the pinned 58x source; its fixed
`p.g.experts` is substituted with 512. It keeps the map traversal, vector `.at`,
projection selection and address/generation stores. Destination arena lookup,
binding, driver calls and waits are deliberately not represented as CPU packing.
Pageable synthetic buffers do not reproduce pinned/GPU-coherent memory costs.

31 trials × 128 iterations, `-O3 -march=native -fno-fast-math -ffp-contract=off`,
nice19, affinity 8–15/24–31. Eight rotating 786,432-byte entry arrays avoid
relying only on one small source array. No cache-drop, settings change or
host-controlled GPU benchmark was used.

| CPU operation | GNU median ms | Intel host median ms |
| --- | ---: | ---: |
| Full pack, one source | 0.059126 | 0.052658 |
| Full pack, eight rotating sources | 0.059510 | 0.052742 |
| Encode 64 supplied dirty IDs | 0.000046 | 0.000082 |
| CPU memcpy of the full staging buffer | 0.022013 | 0.047611 |
| CPU 144-bank scatter (memcpy loop) | 0.290069 | 0.328669 |

CPU copy/scatter rows are diagnostics, **not GPU copy/scatter estimates** and
are not added to projected savings. CPU timing depends on compiler and cache
behavior. The encode measurement excludes discovering/deduplicating dirty IDs.
Full distributions and 32/128-entry encode results are retained in the JSON.

The Intel packing difference is **0.052659 ms**, only **4.28%** of the old
boundary if it transferred directly into the engine. Even this is a model,
not an in-engine host-phase measurement. The remaining **95.72% is unresolved
by that subtraction**, not measured pure synchronization.

The independent 58y raw diagnostic records **1.069387 ms in two publication
wait scopes** and **0.514405 ms of other safe-boundary host work**: waits are
67.52% of that broader 1.583792 ms boundary. The latter includes revocation
construction and fill submission outside 58z's publication clock. Wait scopes
cover the terminal wait plus foreground synchronization; they include transfer
and scatter execution, driver progress and scheduler delay. **They cannot
separate table-byte service time from fixed synchronization.** Importing the
1.069387 ms unchanged into 58z would mix cache sizes and instrumentation.

Thus the exact requested device-byte-versus-fixed-sync fraction is **unknown**.
CPU-only work can establish bytes, calls, packing cost and the ownership
protocol; neither existing receipt supplies that missing causal split.

## Net-removal estimate and gate

60% recovery needs **0.738753 ms/token saved**, leaving at most **0.492502 ms**.
After the CPU packing difference, **0.686093 ms** still has to come from device
work/submission/waits; allow 0.020 ms for new tracking/deduplication/apply
overhead and that becomes **0.706093 ms**. The allowance is an assumption,
not a measured delta implementation. No unknown scatter saving is credited.

For a 64-entry payload, upload size is 2,560 bytes (99.783% fewer H2D bytes),
and device apply writes 3,072 bytes to the tables. Keeping fixed submission,
scatter time and fences unchanged, transferring the CPU packing saving in
full, and charging the 0.020 ms allowance gives:

| Assumed effective H2D bandwidth, excluding fixed costs | Net saved ms/token | Boundary recovery | Projected decode gain |
| --- | ---: | ---: | ---: |
| 4 GB/s | 0.326931 | 26.55% | +0.967% |
| 8 GB/s | 0.179795 | 14.60% | +0.529% |
| 16 GB/s | 0.106227 | 8.63% | +0.312% |
| 25 GB/s | 0.079743 | 6.48% | +0.234% |

Formula: `saving = pack_full - pack_delta + (1179648 - 2560)/(GBps*1e6)
- 0.020` in milliseconds; recompute per-prompt interval rates and class medians.
These bandwidths are sensitivity inputs, **not measured B70 bandwidth or
performance bounds**. Sparse scatter may save additional time or add cost.
At the 16 GB/s assumption it would need another **0.632525 ms/token net** to
reach the gate; no receipt demonstrates it. Unchanged fill timing, delayed
residency and contention are assumptions too. A faster boundary must not be
credited while making later fills or zero-copy misses slower.

**Gate fails on insufficient support for ≥60%, not on a proven hardware
ceiling.** Do not pick the favorable unmeasured remainder and issue a build
brief. The accepted 29.259764 result and all frozen packets remain unchanged.

## CPU proof and reproduction

Both GNU 13.3 and Intel 2026.0 host compilers pass **480 transactions each**
at 96-entry and full 24,576-entry table sizes, with zero/tiny/evicting symbolic
capacities. The test instruments only the two mutation sites in a temporary
copy of `Cache::prepare`; its full plan and final table must match the untouched
cache. Sparse revocation/completion must match full packing byte for byte.
It exercises duplicate routes, empty plans, 6,057 evictions and 6,241
generation-only revocations per compiler. It checks no safe-table pointer
overlaps any fill extent, plus malformed/duplicate IDs, running-reader
refusals, incomplete publication/fills, failed close, and resource-drain guards.
These are metadata checks with fake addresses, not model reads or model tests.

From the repository root, replay saved CPU measurements and receipt arithmetic:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet58ac-cache-publication/replay.py </dev/null
```

Add `--measure-host` to rerun the small host probes. It reads the shared
compiler/whole-host admission helper without modifying `ops`, takes only the
existing `/tmp` compiler lock, and refuses immediately if occupied. All build
outputs live in an automatically removed temporary directory. The CPU probes
completed before a later compiler occupied that lock; two later refresh
attempts refused without compiling. The final receipt replay reuses the
hash-verified saved probes and independently verifies the 58y raw wait sum.
Peak probe/compiler child RSS was **284,916 KiB**; final replay **34,952 KiB**.
The script imposes a 4 GiB address-space cap, asserts affinity/nice/stdin,
and writes only this packet's evidence. No settings, service, GPU, weights,
existing packet, screen tree or live queue was changed.

<!-- campaign-closeout -->

## Question and identity

Can exact changed-entry publication remove ≥60% of packet58z's measured
1.231254 ms boundary and support ≥+2.2% on the unchanged one-card identity?

## Outcome

Closed without a build brief. The CPU protocol supports exact sparse updates;
the time evidence does not support the required net removal.

## What worked

Hash-bound source/receipt replay, exact two-phase dirty tracking, full-table
equivalence and bounded staging reuse. Hot-expert-cache idea credit remains
Niko1221 / Strata as recorded by 58v; this study's code and delta design are
lab-authored and import no external implementation.

## What failed or remains uncertain

The byte-reduction-to-time-reduction inference fails. Current-identity H2D,
scatter, submission and wait costs are unresolved; CPU timing cannot supply
them. Sparse-payload counts, new overhead, device scheduling and complete model
equivalence remain unmeasured. No GPU fault or model experiment occurred.

## Evidence and patches

[analysis.json](analysis.json), [host-probe.json](host-probe.json),
[replay.py](replay.py), [host_probe.cpp](host_probe.cpp), and the frozen input
links above retain all evidence. The small modified metadata header is
reconstructed deterministically in `/tmp`; no runtime patch was adopted.

## When to revisit

A separately authorized, current-identity measurement must separate host
construction/submission, upload, scatter and existing drains without assigning
instrumentation distortion to the candidate. Establish enough reducible device
cost for a complete boundary ≤0.492502 ms/token, including dirty tracking,
fences and fill-cadence effects. Only then brief the implementation, requiring
unchanged-target exactness, generations/lifetimes, two fresh performance starts
and the lane's full cold-suite/determinism gates. Merely demonstrating >99%
fewer table bytes or another CPU mock pass does not reopen this arm.
