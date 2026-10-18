# Packet90: exact expert and HC follow-ups

Preregistered 2026-10-18 before packet86 results. CPU preparation only.
Arithmetic authority: `iq3-p49-split32-v1`, frozen packet49 oracle. Source
base: packet84 record bundle. Control is **hc-wide, wide64, ordered,
rec-parallel**, production route/norm/dense, draft-HC, batch rollback, rank1
draft, 24/24 layers, full BF16 KV. This is an explicit composition, not the
mutable packet84 default (which still selects production recurrence).

## Read the eight packet86 views correctly

| View | Removed work / retained work | What a change can imply |
| --- | --- | --- |
| production | Packet75 wide64 plus attribution; original HC, not this packet’s hc-wide/ordered/rec-parallel composition | Reference for that diagnostic binary only; transfer to packet84 must be measured |
| exp-loadkeep | Exact wide64 with volatile diagnostic metadata/code retention | Cost of enforcing reads; compare ablations to this, and this to production |
| exp-nodeq | Same retained raw-byte reads, but no half/grid decode; unsigned surrogate weights; sums and outputs still computed | Overlapping decode/instruction upper bound, not a pure copy floor |
| exp-constgrid | IQ2 grid magnitudes/signs constant; scale math and chains retained; IQ4 down unaffected | IQ2 lookup/sign dependency cost. **Grid means lookup table, not launch grid.** |
| exp-onecached | Every valid routed slot reads expert zero, with original route validation and all rows/reductions | Repeated-address/locality bound; not proof of DRAM residency or permission to reuse previous responses |
| hc-loadkeep | Exact original Q8 gate arithmetic with retained scale reads | HC comparison control; volatile-read cost must be reported separately |
| hc-nodeq | Raw unsigned code, no signed/scale decoding, scale reads retained | Combined conversion/scale bound; changed downstream activations can confound |
| hc-constscale | Signed code conversion remains, fixed 1/256 replaces scale, scale reads retained | Scale dependency/multiply opportunity; fixed scale is never an exact candidate |

All ablations are non-exact and excluded from quality/performance promotion.
Keep negative deltas, stopped arms and missing sites. Do not add overlapping
bounds. Packet86 used older HC geometry; even its 1.198 ms HC-only historical
reference differs from packet85’s 2.08 ms combined HC/norm/route reference.
Neither licenses calling all 1.75 ms excess removable HC scaling.

## Candidate catalog (expected saving is a hypothesis, ms per target half)

Estimates below are engineering screening budgets, **not measurements or
projections of token speed**. Every range includes a possible regression; the
positive ranges describe the benefit worth testing if the mechanism is present.
Experts total about 2.73/2.75 ms per half in packet77; reuse no roofline-derived
percentage as a result. Exact candidates retain the 32 logical chains, each
chain’s k/j order, adjacent reduction tree, separate FP32 multiply/add, original
BF16 stores, route/status/error behavior and every unchanged verifier operation.
No FMA, compressed KV, changed quantization, routing shortcut or approximate
math. All weight transformations must reproduce the original decoded FP32 bits.

| ID / priority | Mechanism | Expected saving / half | Risk and gate |
| --- | --- | --- | --- |
| E1 **build now, #1 expert** `exp-halfcache` | During the existing IQ2 gate/up repack, replace each 16-bit half-scale with its exact decoded FP32 value. Decode once per immutable weight block. Keep codes/grid/signs, `(d*(0.5+q))*0.25`, products, sums and wide64 geometry unchanged. IQ4 down unchanged. | 0.15–0.55 ms; zero/regression possible | +301,465,600 bytes on rank 0 / +314,572,800 on rank 1, more traffic and possible compiler CSE already doing most work; exhaustive finite-half byte gate and actual stride/extent startup test |
| E2 `exp-scalecache` | Store the sixteen exact FP32 effective IQ2 scales per 256-weight block, evaluating the original two multiplications at load time; runtime loads same bits | 0.25–0.80 ms if scale-bound | Large resident growth exceeds current margin if applied to all gate/up weights. Design only: must prove admission via bounded per-layer device preparation before sealing; extra launch/read may erase benefit |
| E3 `exp-grid-prefetch` | Issue the next IQ2 grid-word load before consuming the current tile, buffering only two raw grid words per logical chain; no FP32 sums moved | 0.20–0.65 ms if dependent lookup latency dominates | Register/flag spill, p73 raw-code lookahead was not this grid-dependency mechanism; require linked register census before device screen |
| E4 `exp-slot-coalesce` | Group only duplicate expert IDs within the **current token**; compute each identical gate/up projection once and scatter to original slot outputs/status. Down still uses distinct per-slot activations | 0–0.45 ms, zero if router guarantees unique IDs | Production router likely selects unique experts: prove duplicate frequency on existing evidence first; otherwise close. Never cross-token reuse or altered route order |
| E5 `exp-gate-up-shared-input` | A single subgroup carries separate gate and up logical sums and loads shared activation bits once; preserve each independent chain/tree | 0.10–0.45 ms if locality stalls dominate | Higher register pressure; unlike closed p81 it changes gate/up scheduling, not packed activation load width. Requires new p86 latency evidence and no spills |
| H1 **build now, #1 HC** `hc-weightcache` | At load, materialize `scale*float(signed8(code))` as FP32 for target HC up/gate weights only. Keep hc-wide two-row geometry, activation product, chain, tree, BF16 gate and mix unchanged | 0.15–0.60 ms if scale/conversion dominates | +442,368,000 bytes/rank; gate read traffic grows. Preserve scale multiply before activation multiply, signed zero and finite/subnormal bits; full-size admission required. Draft/final HC unchanged |
| H2 `hc-scale-broadcast` | In existing hc-wide subgroups, a leader loads the unchanged FP32 scale for each four-lane Q8 block and broadcasts identical bits; preserve each lane’s conversion/multiply | 0.05–0.25 ms if redundant scale dependencies dominate | Shuffle overhead may cost more; same geometry, no four-stream virtual HC. Require device counters/latency evidence before reopening a load-oriented arm |
| H3 `hc-low-gate-fuse` | Fuse low/activation into each existing gate workgroup with exact original split4 low reduction and BF16 activation boundary; duplicate only bounded low work, retain global low/act/inject outputs with unique owners | 0.10–0.40 ms if separately established launch overhead dominates | Potential huge duplicated low GEMV work; reject if cost exceeds launch budget. No cross-workgroup spin, no new reduction order |
| H4 `hc-tiled-f32` | Apply H1 only to alternating, explicitly pinned layers, or tile its FP32 gate reads through the same two-row subgroup to bound bandwidth growth | 0.05–0.30 ms, conditional on H1 mechanism | Partial application must be deterministic and layer IDs fixed before timing; no cherry-picking winning prompts. This is a new design, not a claimed H1 result |

H1 and E1 are separate views plus production, **no combined view**. Combined
memory and speed are not implied by separate admission. These two remove
immutable decode work regardless of whether the next ablation attributes most
cost to decoding or dependencies, without reopening the closed packed-load or
four-stream-geometry sweeps. They are ranked first by implementability, exactness
proof and available memory, not a presumed positive packet86 outcome.

## Verdict → next candidate to seal

Use complete, same-lane p86 site-call measurements and both loadkeep controls.
A practical material signal is >=0.15 ms/half and >=5% of that site, consistent
in both lanes; smaller/inconsistent effects are inconclusive, not proof of no
cost. This threshold is a preregistered triage rule, not statistical significance.
If only one lane completes, keep attribution provisional and use a bracketed
exact screen; do not silently substitute incomplete diagnostic rows.

| Possible verdict | Evidence pattern / implication | Exact candidate order (2–3 choices) |
| --- | --- | --- |
| Expert remaining dequant-bound | loadkeep−nodeq material; constgrid−nodeq retains material decode cost | E1 → E2 (only after memory proof) → E3 |
| IQ2 table/sign dependency-bound | loadkeep−constgrid material, larger than residual decode budget | E3 → E1 → E5; constgrid alone says nothing about launch count |
| Expert repeated-address/cache/load-bound | production−onecached material, decode deltas small or secondary | E5 → E3 → E4 (only if real routes duplicate; otherwise closed) |
| Expert launch/geometry-bound | All expert ablations small, and **separate** event-count/launch evidence identifies fixed overhead | E5 → E3; no geometry sweep from a residual roofline gap, no launch verdict from p86 alone |
| HC scale-bound | hc-loadkeep−hc-constscale material | H1 → H2 → H4 |
| HC signed conversion / remaining dequant-bound | hc-constscale−hc-nodeq material | H1 → H4 → H2 (only with scale dependency evidence) |
| HC cache/load-bound | Scale/decode deltas small and separate measured bandwidth/latency supports loads | H2 → H4; do not infer this solely from a small non-exact delta |
| HC launch/norm/route-bound | HC ablations small; separate measured event costs locate launch/norm/route instead | H3 → H2 (only measured scale redundancy); no claim to optimize norm/route with a gate-only candidate |
| Mixed expert+HC | Material signals in both, non-additive | E1 and H1 separately first; then E3 or H2 according to the larger bound |
| No clear signal / contradictory lanes / faulted or nonfinite arms | Cannot rank a limiter reliably; report missing values and retention overhead | Bracket E1 and H1 exactly once; then E3 only with linked-code latency evidence. No blanket rerun of closed arms |

## CPU and coordinator gates

1. Freeze parent source hashes; copy, never edit packet84. Byte tests run GNU
   and Intel twice, comparing raw FP32 decode/chain/tree values and BF16 outputs,
   including zeros, subnormals, exceptional activations, routes and errors.
2. Build serially on cores 8–15,24–31 at nice19, <=8 GB address space and <1 GB
   build. Coordinate turns with packet58g. No device binary execution here.
3. Full-shape startup follows the real two-rank allocation, selection,
   preparation, snapshot and draft-constructor paths. Mock only device storage
   and payload reads. Validate actual transformed strides/extents and negative
   short/misaligned allocations; run unchanged memory admission on each census.
   Test closed-environment worker imports and real lane admission in temporary
   roots. New choice values must either pass supported selection consumers or
   explicitly refuse unsupported chain/promotion use.
4. Seal every view with exact source/binary/fixture/placement bindings. Use only
   the hash-pinned shared `screen/v4-lanes` wrapper. Plan proposed queue files
   on a temporary queue; do not enqueue or launch them.
5. Coordinator uses the pinned wrapper’s built-in **one prompt ×64-token**
   startup oracle gate for each new path before any timed suite (stronger token
   coverage than the memory note’s 32-token minimum; no modified wrapper).
   Then production / exp-halfcache / hc-weightcache / production full screens on lane A,
   exact improving winner bracketed on the other. Complete fixed-suite oracle,
   status, acceptance and no-regression checks required; two fresh owners before
   speed verdict. No retries and no automatic chain promotion.

Closed: p67 roofline-picked/four-stream HC, p74 packed dense, p81 packed
activation load-count, p83 draft bytes. Read their DO-NOT-REPEAT records before
this preregistration. No external code or model download. Candidate saving and
device correctness remain unmeasured until coordinator-owned exact screens.

Implementation review before sealing: both caches reject unsupported runtime
modes before device creation; the combined layout is refused. HC nonfinite
weight scales explicitly refuse at load (matching the IQ2 finite-scale boundary),
not silently converted. Native plan bytes and full-size arena bytes must agree.
