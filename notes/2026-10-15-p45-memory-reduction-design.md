# Packet45 SPEED6 memory design — unapplied

**Reduce target operator scratch to 8 MiB for 23/25 dr1 at 4K, and check the
30 GiB arena during window admission.** That leaves **85.22 MiB inside the
arena** and **589.54 MiB above the separate 1.5 GB card reserve** on rank 1.
No weight offload, precision change or kernel change is needed for this arm.

The [implementation patch](../patches/packet45-speed6-memory.patch) is **not
applied**. The packet tree, its running SPEED5 windows, binaries and seals were
read only. No compiler, device binary or device-discovery call ran. All Python
used `python3 -B`, nice 19, ionice 3, cores 4–15,20–31 and OMP_NUM_THREADS=2.
Only this note and the patch are committed. Source baseline is SPEED5
`887a0bbbe1753a20cb4c7d3d9948016b66b06ac6`; repository HEAD when analysis began
was coordinator ledger commit `a7acbe3ec`.

My [split design](2026-10-15-p45-split-sweep-design.md) called 23/25 dr1
admissible after checking the card reserve alone. That conclusion was wrong:
`Engine::allocate` has an independent, stricter arena cap. The performance
forecast was not a device measurement and remains untested.

## Exact accounting of the refusal

All numbers below are bytes unless marked MiB; 1 MiB = 1,048,576 bytes.

- Engine arena cap: **32,212,254,720** = 30 GiB, `main.cpp:721–730`.
- Card capacity: **34,242,297,856**; mandatory reserve: **1,500,000,000**.
- The memory ledger also reserves **46,500,548** on rank 0 and **1,228,800** on
  rank 1 for conservative accounting. These are not Engine allocations.
- Pinned staging is host memory, excluded from `owned_bytes` and the arena.

The two incident `W2m/run/rank1.log.gz` files are byte-identical and print:

```text
card 0 owned_bytes 29028573034 weights 28640544512 dispatch r5
```

Here `card 0` is the rank-local card index. **29,028,573,034 already includes
target caches, workspaces and operator scratch.** `write_plan` adds them before
printing, at `main.cpp:1374–1398`. It omits the later draft allocation. Adding
the draft's **3,354,364,214** produces **32,382,937,248**, or **170,682,528
bytes / 162.776 MiB over the arena**.

There is no completed rank-1 incident census: draft construction throws at
`rank.hpp:228`, before census emission at `:229`. The rank-1 total below is an
exact reconstruction from the incident launch metadata and complete SPEED3
census, not a claimed measurement of allocations that never completed. Rank 0
has a complete incident census. The 25/23 rows are counterfactual metadata
projections; that split was not launched.

| Device category, 4K | 23/25 dr1 r0 | 23/25 dr1 r1 | 25/23 dr0 r0 | 25/23 dr0 r1 |
|---|---:|---:|---:|---:|
| Target weights, excluding RoPE | 25,798,503,168 | 28,640,544,512 | 28,018,344,576 | 26,420,703,104 |
| Immutable RoPE table | 4,194,304 | 4,194,304 | 4,194,304 | 4,194,304 |
| Draft weights, excluding duplicated head | 0 | 3,326,953,472 | 3,326,953,472 | 0 |
| Additional draft output head | 0 | 0: shared | 839,321,600 | 0 |
| Target KV/QSA cache | 48,496,640 | 67,895,296 | 58,195,968 | 58,195,968 |
| Draft KV/QSA cache | 0 | 9,699,328 | 9,699,328 | 0 |
| Recurrent state, including alternate banks | 59,203,600 | 29,417,472 | 62,472,208 | 27,783,168 |
| Operator scratch | 268,435,456 | 268,435,456 | 268,435,456 | 268,435,456 |
| Target workspaces, outputs and controls | 17,120,598 | 18,085,994 | 17,683,638 | 17,522,954 |
| Draft workspaces, outputs and controls | 0 | 17,711,414 | 17,711,414 | 0 |
| Private snapshot backup | 363,654,210 | 0 | 375,550,882 | 0 |
| **Engine arena total** | **26,559,607,976** | **32,382,937,248** | **32,998,562,846** | **26,796,834,954** |
| Host-pinned staging/publication, excluded above | 4,194,304 | 4,214,796 | 4,214,796 | 4,194,304 |
| Ledger accounting reserve, excluded from arena | 46,500,548 | 1,228,800 | 46,500,548 | 1,228,800 |

Shared IPC storage is another 200,704 host bytes per pair, not a device arena
allocation. Draft workspaces include its existing 8 MiB scratch and exact-size
7,946,240-byte head workspace; they are not additional uncounted categories.

| Configuration/rank, 4K | Arena headroom before | Card headroom above 1.5 GB reserve before | Device saving from scratch + backup | Arena headroom after | Card headroom above reserve after |
|---|---:|---:|---:|---:|---:|
| 23/25 dr1 r0 | 5,652,646,744 | 6,136,189,332 | 520,093,696 | 6,172,740,440 | 6,656,283,028 |
| **23/25 dr1 r1** | **−170,682,528** | **358,131,808** | **260,046,848** | **89,364,320** | **618,178,656** |
| 25/23 dr0 r0, hypothetical | −786,308,126 | −302,765,538 | 520,093,696 | **−266,214,430** | 217,328,158 |
| 25/23 dr0 r1, hypothetical | 5,415,419,766 | 5,944,234,102 | 260,046,848 | 5,675,466,614 | 6,204,280,950 |

Thus 25/23 dr0 needs **786,308,126 bytes / 749.882 MiB**, not merely the
302,765,538 bytes needed for the card reserve. The proposed technique, if
extended to that arm, would still leave **253.882 MiB** of arena deficit.
The patch does not enable split25 or shrink its allocations.

The reconstruction uses the existing embedded C256 allocation census and
source-derived context deltas in `memory_plan.py:186–265`. One QSA layer is
`2368 × context` bytes: keys + values + raw index + pooled index. At 4K it is
9,699,328 bytes. Boundary 23 moves QSA layer 23 from rank 0 to rank 1: target
QSA counts become 5/7, and the draft adds one cache on its placement. Moving
GDN layer 24 onto rank 0 for hypothetical boundary 25 adds 1,115,963,658
target bytes, 1,634,304 alternate-bank bytes and 1,917,322 snapshot bytes.

## Why the scratch reduction is lossless

The existing **120/120** SPEED5 plan/dispatch rows all report a maximum
operator-scratch footprint of **1,597,440 bytes**. These cover target rank 0,
target rank 1, KD and draft plans, both contexts, all five admitted placement
specifications, and device dr0/dr1 plus forced dispatches. Every source hash in
that retained proof still matches the running source. This is a checked
metadata/kernel bound, not a measured profiler peak.

The largest requirement is the QSA value reduction:

```text
6144 × ceil(min(context, budget + 3) / 32) × sizeof(float)
= 6144 × 65 × 4 = 1,597,440 bytes, for budget 2048
```

The 8 MiB choice retains **6,791,168 bytes** beyond that bound. It is deliberately
larger than the minimum: allocating exactly 1,597,440 buys only another 6.477
MiB of arena margin. The old 256 MiB cap is unused capacity for these parallel
plans, not state that the speculative half needs to preserve.

`SnapshotWriteSet::scratch` (`strict_snapshot.hpp:35–67`) bounds possible
writes. For allocation sizing the proof must also cover **reads**: the proposed
plan gate checks those bounds against `specialised::scratch_floats` and
`round2::scratch_floats`, the full addressable requirements used by the
specialised, round2, p33r2 and p42 submitters. The actual binding guards remain
at `specialised_submit.cpp:31–32`, `round2_submit.cpp:60`, `p33r2.cpp:37` and
`p42_submit.cpp:45`. QSA value writes and reads the same bounded partial array;
the other parallel operators use bounded prefixes, private/local storage, or
no operator-scratch access (`adapter.cpp:265–324`). GEMV's separate workspace
is unchanged. No kernel indexing, reduction order or candidate choice changes.

The patch checks the plan before backend construction. Unknown operators or
unproved geometry in the reduced arm refuse, rather than silently falling back
to a larger allocation while the ledger credits a reduction. Reference
`--nongemv core` retains 256 MiB: its interpreter advertises a 64M-float pool
at `runtime_kernels.hpp:131`. Other production placement/context combinations
also retain their original sizes. The small synthetic 23/dr1 plan exercises
the reduced path in the future mini gate.

Rank 0 receives a second saving automatically. `SpeculativeImage` reserves
the full capacity of each source allocation (`strict_snapshot.hpp:191–197`),
so shrinking scratch by 248 MiB also shrinks its private backup by 248 MiB.
The backup goes from 363,654,210 to **103,607,362 bytes** for 23/25 dr1 at 4K.
The write-set capture and restore payload stays unchanged; no snapshot extent,
inactive bank, invalid cache tail, metadata, sticky error or ownership check
is dropped. The CopyEngine 128 MiB guard is unchanged. Initialization and
private-backup clearing can do less work; no steady-state per-step saving is
credited to those boundary operations.

## Other reductions, ordered by usefulness for this refusal

| Choice | Bytes saved on the blocked rank | Expected speed cost and proof requirement |
|---|---:|---|
| **Target scratch 256→8 MiB** | **260,046,848** | No extra launches/transfers or arithmetic changes; retain lifetime and read/write extent proof. Enough by itself. |
| UVA: 64 draft experts | 393,216,000 | Bandwidth-only projection 0.404–1.097 ms per draft evaluation under uniform routing; new runtime binding work. More capacity, worse tradeoff than scratch. |
| UVA: 32 draft experts | 196,608,000 | 0.202–0.549 ms projected; only 24.72 MiB arena margin if used alone. |
| UVA: 128 experts of target GDN layer 24 | 252,313,600 | 0.259–0.704 ms projected per layer evaluation; routing and alignment proof needed. |
| Draft scratch 8 MiB→1,597,440 bytes | At most 6,791,168 | Additional private merge-path bound required; no arithmetic saving. Not needed. |
| Target GEMV workspace 8 MiB→head requirement | At most 442,368 | Head requirement is 248,320 × 8 × 4 = 7,946,240; all selectable recipes must still fit. Too small to fix this. |
| Compact snapshot backup to maximum capture union | **0 on rank 1** | Rank 0 could save another 55,275,008 after the scratch change: 103,607,362→48,332,354. Needs maximum-position/cancel/redo packing proof; cannot solve this rank-1 deficit. |
| Deduplicate draft output head | **0 additional on dr1** | Already aliases resident target `output.weight`, `mtp.hpp:150–151`. |
| Deduplicate full embedding allocation | **0** | No duplicate full device embedding: lookup reads a bounded host row. |
| Shrink the 4 MiB staging slab | **0 device bytes** | Host-pinned at `main.cpp:849–851`; shrinking it would add upload chunks. |

The snapshot alternative's 48,332,354-byte union was calculated from the
incident rank-0 launch/census metadata and the matching three dispatch proof
rows, replacing full QSA capacities with their one-row writer bounds and
operator scratch with 1,597,440. No runtime packing change is included.

Dr0's additional head is **839,321,600 bytes** on a different physical card
from the target head. It cannot be deduplicated with a pointer alias. Reading
that full head over PCIe for every draft would take about **44–120 ms** at
the illustrative bandwidths below. Executing the head remotely on rank 1
instead would require a separate scheduling/handoff design, with its own
private workspace and serialization costs. Neither is a cheap substitute for
scratch sizing, and neither is in this patch.

### UVA frequency and transfer cost

Both target and draft route to 10 of 512 experts. An expert's gate/up/down
triplet occupies **1,971,200 bytes** in target layer 24 and **6,144,000 bytes**
in the official INT8 draft layer. All experts must remain accessible; host
placement cannot prune, quantize, cache an answer or change accumulation order.

No retained packet45 census provides per-expert routing frequencies. It would
be dishonest to label a particular subset “cold” from allocation metadata.
For a host set H, expected traffic per layer invocation is
`sum(P(expert i selected) × stored_triplet_bytes_i, i in H)`. The following
numbers assume uniform selection, `P=10/512`, and **illustrative effective
bandwidth of 19–7 GB/s**, not a measurement of this packet's PCIe path:

| Host set | Device bytes saved | Expected host hits per invocation | Payload per invocation | Transfer time, 19–7 GB/s |
|---|---:|---:|---:|---:|
| 32 draft experts | 196,608,000 | 0.625 | 3,840,000 | 0.202–0.549 ms |
| 64 draft experts | 393,216,000 | 1.250 | 7,680,000 | 0.404–1.097 ms |
| 128 target-layer24 experts | 252,313,600 | 2.500 | 4,928,000 | 0.259–0.704 ms |

For the rank-1 placement, approximately one draft and one rank-1 target
evaluation occur per emitted position; startup/end effects need actual counts.
If a half is speculated and redone, multiply by its evaluations per emitted
token (about 1.209 at 79.1% acceptance for a half redone on each miss).
The table excludes latency, transaction amplification and pointer indirection.
Worst-case routing of ten host draft experts moves 61.44 MB per invocation,
or **3.23–8.78 ms** before those additional costs. Fixed routing-independent
availability and a broad routing census are necessary for any later UVA arm.

The earlier [FP8 lane experiment](../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)
at “23:50 per-expert placement” found bit-identical outputs on 32 routings,
roughly 0.1 ms per host-expert hit, and a 3× resident-row slowdown when pointer
alignment information was lost. Its following realistic-suite census assigns
0.035% of hits to the coldest 10%. Those are that lane's measurements, not
packet45 routing probabilities or a proof for its quantized arithmetic.

`owner.cpp:167,189` currently requires device allocations for compute and
prepared bindings. Correct UVA support would need a narrowly typed immutable
host binding, pinned lifetime through completion, per-expert addresses with
the same layout/alignment, and validation on all routings. It must not relax
ordinary owner checks or simply mark a pinned slab as device memory.

## Admission repair and patch contents

The current `window.py:351–352` already calls `memory_gate.configuration`
before environment/device admission or output creation. The patch makes that
call compute, for **every configuration including default splits**:

```text
arena = target_modeled_allocations_bytes
      + draft_total_bytes + draft_duplicate_head_bytes
arena <= 30 × 1024^3

card_live_ceiling = arena + allocation_reserve_bytes
capacity - card_live_ceiling >= 1,500,000,000
```

Component consistency is checked; summary booleans cannot authorize an
over-capacity row, and the ledger cannot raise the arena cap. The old ledger
also fails correctly without any new arena-summary fields. Live census checks
retain their existing extent/plan/reserve checks and additionally enforce the
arena limit. These checks also run in diagnostic-unsealed mode.

The changed files inside the **unapplied** patch are `main.cpp`,
`memory_plan.py`, `memory-plan.json`, `memory_gate.py`, `test_speed5.py`, and
new `test_speed6.py`, `speed6_memory_gate.py`, `speed6_plan_gate.py` and
`speed6_snapshot_gate.py`. The generated memory ledger credits savings only
for **parallel 23/25 dr1 at 4096**; its arena and reserve fields are separate.
Default 22/26 dr0, 24/24 dr1, explicit 24/24 dr0 and 23/25 dr0 retain their
old allocations and admissible contexts.

**32K remains refused.** Even hypothetically extending the scratch reduction
to 32K leaves rank 1 at **32,666,052,768 bytes**, **453,798,048 bytes over
the arena**. Its card reserve would then pass by 75,016,288 bytes, another
example of why these checks cannot be conflated. The actual patch does not
extend the reduction or context allowance to 32K. Split25 remains unsupported.

No parser, split, arithmetic, dispatch, mailbox ABI, rollback algorithm,
watchdog, boot latch, teardown or exact-token comparison changes. A future
build will change host and device executable hashes because `main.cpp`
allocations change; it does not change kernel arithmetic. **No artifact hash
or seal changed in this design session.**

## Validation and future qualification

Executed now, using an in-memory Python source overlay with an audit hook
that forbids all packet45/packet44 filesystem mutations and process launches:

- **23/23 unit tests**: nine existing split tests plus fourteen arena tests.
- All **21 window types × 2 provenance modes = 42** legacy-overrun cases
  refuse before output creation or environment/device admission.
- Exact incident reconstruction, arena boundary and one-byte overrun,
  component/boolean/cap mutation controls, live census, pinned-memory
  exclusion, all existing admitted configurations, and independent reserve
  and 32K refusals pass.
- All seven proposed Python files parse. The future C++ metadata harness was
  generated into external scratch and inspected; its compiler invocation was
  deliberately intercepted. **No C++ compilation or new mini execution ran.**
- `git apply --check patches/packet45-speed6-memory.patch` passes without
  applying the patch. Retained production evidence gives 120/120 metadata
  bounds, not fresh runtime qualification.

After the queue stops and this design is selected, apply the patch and rebuild
the changed runtime under the host rules. The included producers require a
fresh **120-row** plan/dispatch sweep and the existing **62 mini executions /
52 state checks, including four negative controls**, for both split23 draft
placements and both controllers. The new mini producer checks the actual
census: dr1 uses 8 MiB and the dr0 control keeps 256 MiB. It compares full
state for hits, misses, wrong guesses, request/terminal boundaries, cancelled
prefixes, redo and abandoned redo. The metadata producer checks kernel
read/write requirements, unknown-footprint refusal and reference-size retention.

The future commands, only in a stopped and rebuilt tree, are:

```bash
P=experiments/own-xpu-runtime/stage2/packet45-merged3
cpu=(nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B)
"${cpu[@]}" "$P/speed6_memory_gate.py"
"${cpu[@]}" "$P/speed6_plan_gate.py"      # one metadata-only compiler job
"${cpu[@]}" "$P/speed6_snapshot_gate.py"  # rebuilt CPU-host binary, mini only
```

The patch deliberately does not forge receipts or repin the existing seal to
untested sources. Existing seal pins will reject it until the exact source
delta and these fresh gates are bound in the minimal seal-6 amendment workflow.
No real-model CPU rerun or compiler matrix is proposed. Device windows W2m,
WS, WSs and WS128x remain the real-model exactness authority. Applying the
patch alone is not authorization to launch with a stale binary or seal.

## Performance forecast and cheapest confirmation

| Configuration at 4K | Predicted hit | Predicted miss | Predicted class-balanced tok/s | Decision |
|---|---:|---:|---:|---|
| 23/25 dr1 with bounded scratch | 22.03 ms | 38.89 ms | **39.61** | One qualifying arm, then matched A-B-A if promising |
| 24/24 dr1 | 22.87 ms | 40.43 ms | 38.13 | SPEED3 measured anchor for the split model |
| 25/23 dr0 with this technique | — | — | No admissible prediction | Still over arena; not implemented |

The first row carries forward the [split cost model](2026-10-15-p45-split-sweep-design.md):
about **0.84 ms per hit and 1.55 ms per miss** saved relative to its dr1
anchor. Scratch allocation itself earns **zero additional forecast saving**.
The prior 39.04–40.19 tok/s sensitivity range is not a confidence interval;
the receipts do not separate QSA and GDN layer costs, and selected dispatches
and card-pair timing can differ. Do not credit an unmeasured SPEED4/SPEED5
improvement or present 39.61 as a new result.

The cheapest useful device check is the full existing 23/25 dr1 qualifying
chain at 4K, keeping the fixed cold suite and oracle unchanged. First confirm
rank-1 live census stays within the new bound before HALF. For speed attribution
use 24/24 dr1 → 23/25 dr1 → 24/24 dr1 on the same pair and boot, and disclose
any K2 dispatch difference. Cross-pair repetition decides whether a gain is
placement or card variation. Do not reuse an old exactness receipt as a new
performance qualification.

## Evidence identities

All packet paths below are relative to
`experiments/own-xpu-runtime/stage2/packet45-merged3/`.
Incident prefix: `build/incident-20261015-speed5-split23-arena/`.
Both `speed5-c4096-dr1-s23-cards01-gpu/` and `...cards23-gpu/` have identical
rank census/plan/log bytes used here.

| Read-only input | SHA256 |
|---|---|
| Incident `W2m/run/rank0/census.json` | `5f70cb9dd1a2cd6a7549263d7a77dd805786d554c7e44b21b1bf679b73730b10` |
| Incident `W2m/run/rank0/launch-plan.json` | `7a29e4b02662799f2bdb711df64b0d5f9cc40a0aa28d9740e82b2274d10461e9` |
| Incident `W2m/run/rank1/launch-plan.json` | `6426b6c84fbf668fa5c287e767a09b605eb71c70ead56756a15e20e8d534b57f` |
| Incident `W2m/run/rank1.log.gz` | `72ed4874906af64875c076221027a7bd1481783c91b28dd7d0178a37bf8d5990` |
| SPEED3 24/dr0 rank0 census | `5da4e07e19c242a8e1fb5c278823a2d717f4471eb005554b4abd330111b65a30` |
| SPEED3 24/dr0 rank1 census | `6df7f434abcbbd93b889199d4c79ea08197bfc3b6745ad4db9f8008f9612a673` |
| SPEED3 dr1 rank0 census | `128920cfb72982b0d7b0968f1a5fcebea84eaf13a946e6e1a50e7fb4dbf1221e` |
| SPEED3 dr1 rank1 census | `f9fdedcc867f6d6f0e70dd8df61e93155d731bc653afaf4466f3e9fc469142b4` |
| `speed5-plan-gates.json` | `09a17422cd20a2c9ad4c905857b005a4531cc9a45f2a909e8e4cd1bac57b4b6d` |
| `evidence/speed5/plan-writer-sites.json.gz` | `6c74e54e739632ef2fc30e1e98ff4162df434725b7ea6be7184ddcc110d0bcb5` |
| Model metadata `build/input/plan.tsv` | `9926b7a266ba2774f02fe00583257ab2aaff96ee0313d350d3ba54602ae2a656` |
| Original `memory-plan.json` | `2a1458c0ce692ba4edf3b55068d454f8aa2356ee543020d033145599955cb285` |

SPEED3 census suffix is `WS128/run/ranks/rankN/census.json`, under
`build/speed3-c4096-dr0-s24-gpu/` or `build/speed3-c4096-dr1-gpu/`.
Patch SHA256:
`844f9e8ec7d96efb4abbcd5f6c1899bd473ff2906a7e97e24b5d9b1991f3f1c5`.
