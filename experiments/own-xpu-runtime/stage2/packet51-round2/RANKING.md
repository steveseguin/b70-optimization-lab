# Packet 51: remaining exact-order opportunities

This is source diagnosis and planning arithmetic, **not a measured speedup**.
No model payload or GPU was opened for this census. The starting timings are
the first fresh owner's `ordinary_gdn.class_median_gpu_us.specialized` values
in [p48b's retained summary](../packet48b-production/evidence-copy/p48b-a-summary.json).
The second owner is retained there too; the first is used consistently rather
than taking the best class value across owners. Bytes and layer membership
come from [packet48's census](../packet48-gemv/byte-census.json) and
[its definitions](../packet48-gemv/BYTE-CENSUS.md).

One important control distinction: p48b measured all four replacement classes,
but its summary selects **only expsgate and expsdown** as integration candidates.
The 96.667/37.188 us QKV/Z values below describe that measured p48b arm; they
do not mean packet49 adopted those replacements. Packet51's matched baseline
must retain the actual chosen dispatch, not silently give p48b's QKV/Z
candidate the status of an accepted production kernel.

## Ranking and the layer multiplier

For weight-dominated rows, `floor_us = useful_weight_bytes / 550000` and
`gap_us = measured_us - floor_us`. This deliberately optimistic bound excludes
decode instructions, repeated loads, activation reads, scratch, controls,
BF16 stores and launch cost. The numerator is distinct useful payload, not
measured DRAM traffic. The 550 GB/s reference is the owner's planning ceiling.

| Class | M=1 time us | Useful weights MB | Weight-only floor us | Optimistic gap us/call | Gap × 48, ms | Matching layers; corrected gap ms |
|---|---:|---:|---:|---:|---:|---|
| HC set, both sides, mixed compute | 130.001 | 15.155 | 27.555 | **at most 102.446** | at most 4.917 | 48; at most 4.917 |
| IQ2_S expsgate pair | 77.292 | 10.496 | 19.084 | **58.208** | 2.794 | 47; 2.736 |
| Route, compute/ranking | 43.644 | 0 | not a bandwidth model | **less than 43.644**, compute floor unmeasured | less than 2.095 | 48; less than 2.095 |
| IQ4_NL expsdown, already improved | 54.375 | 9.216 | 16.756 | 37.619 | 1.806 | 48; 1.806 |
| GDN QKV, Q6_K | 96.667 | 32.768 | 59.578 | 37.089 | 1.780 | **35**; **1.298** |
| Attention output projection/combine | 57.812 | 19.661 | 35.747 | 22.065 | 1.059 | 48; 1.059 |
| Small FFN tuple, Q6_K shared projections | 27.500 | 9.349 | 16.998 | 10.502 | 0.504 | 47; 0.494 |
| Shared down | 10.938 | 1.843 | 3.351 | 7.587 | 0.364 | 48; 0.364 |
| GDN Z, Q6_K | 37.188 | 19.661 | 35.747 | 1.441 | 0.069 | **35**; **0.050** |

The HC line sums class medians; it is not the median of per-iteration sums.
It is suitable for this budget, not a replacement performance statistic.
Its low/gate/inject GEMVs account for 94.062 us, and norm/mix for 35.939 us.
The 102.446-us bound is especially loose: tiny low-rank and nonlinear work
cannot be priced by aggregate bandwidth. A timing run must sum the classes
inside each iteration before taking its median.

The model has **36 GDN layers and 12 QSA layers**. Layer 2 is the GDN format
exception: IQ3_S routed gate/up (14.080 MB), and Q8_0 QKV/Z
(29.491/17.695 MB useful expanded payload). Ordinary Q6 QKV/Z therefore have
35 matching layers, not 48 or 36. IQ2_S expsgate and the Q6 small-FFN tuple
have 47. Output projection/combine uses the same Q6 shape in both GDN and
QSA and has 48 matches. These multiplications are hypothetical serial
per-target-position savings; they cannot be converted to emitted tok/s or
added as though the two engine halves had no overlap.

Other remaining compute classes:

| Class | Time us | Compute/state diagnosis | Honest time budget |
|---|---:|---|---|
| GDN recurrence | 35.938 | 48 × 128 state rows, each 128 wide; two normalization dots, prediction/output dots, decay and BF16 state update; tokens are recurrent | Less than 35.938 us/call; less than 1.294 ms across its 36 layers; no calibrated compute floor |
| FFN combine | 11.198 | Ordered stream blend and sigmoid, BF16 boundaries; little weight traffic | Less than 11.198 us/call, less than 0.538 ms across 48 |
| HC norm/mix subset | 35.939 | Four-stream ordered mix plus reductions and nonlinear operations | Included in HC above, never add twice |

No sustained instruction/divide/transcendental rate was measured for these
classes. Assigning a numeric compute floor from an unrelated peak-FLOP number
would invent precision. Their ceilings above explicitly leave positive
arithmetic time unpriced. Source operation counts below identify mechanisms
that can reduce work without changing the model; coordinator timings decide
the recoverable fraction.

## Execution priority

1. **IQ2_S expsgate** remains first: the largest clear packed-kernel lever,
   with 58.208 us of optimistic headroom and a direct 1.5x bar. At the
   starting 77.292 us, that bar means at most 51.528 us, saving 25.764 us
   per matching layer (1.211 ms over 47). It need not meet the alternative
   40-us complete-layer bar by itself.
2. **HC**, treating its 102-us ceiling as a mixed-work budget. Prioritize
   repeated instructions and undersized occupancy; blanket launch fusion
   already had a neutral result in packet46.
3. **Route**, whose current denominator/ranking repetition supplies a
   concrete compute lever. It can contribute meaningfully to the combined
   40-us bar without pretending that zero weight bytes imply zero cost.
4. **GDN QKV**, ahead of attention on corrected headroom (1.298 vs 1.059 ms).
   This is a modest reordering of the brief's last two targets. Target load
   and row geometry; the existing tree is fixed.
5. **Attention output/combine**, where per-row repeated sigmoid evaluation
   is a separate lever from dense loads.

Keep expsdown as the accepted p48b control for this round. It has a useful
remaining budget but already gained 1.68x; the classes requested for round2
have more distinct untested mechanisms. Z at M=1 is a small lever and is
deferred. Recurrence is a later compute-normalization sharing experiment,
requiring its own state and multi-token gate.

## Source diagnosis of the five targets

**IQ2_S gate/up:** [p48 gemv.hpp](../packet48-gemv/gemv.hpp) `decode8` and
`gate_lane`, bound by [p48b candidate.hpp](../packet48b-production/candidate.hpp),
still assign one SG32 to one output row. At K=2560 each lane walks ten tiles
of eight values. Each projection separately loads packed index/sign metadata,
half and nibble scales, two indexed codebook words, signs and converts eight
values. The paired kernel shares activation loads but keeps two ordered
accumulators. Repacking made loads aligned; it did not eliminate table gathers,
scale/sign work or the 80 dependent additions per lane/projection. This is why
135.8 GB/s of *useful-byte accounting* does not diagnose a saturated DRAM bus.
The observed 1.062x/1.059x gain is consistent with remaining instruction and
dependent-load cost, not proof of which one dominates. Candidate mechanisms:
encode reusable decode work outside the hot loop, or improve row occupancy
and loading while retaining every product/add and SG32 tree. Any larger
expanded payload must be counted honestly and admitted against device memory.
Do not split the K sum or reassociate it to claim exact order.

**HC:** [p30_small.hpp](../packet45-merged3/p30_small.hpp) exposes low as
320×10240 Q8 split-four, gate as 10240×320 Q8 split-one, and inject as
4×10240 F32 split-four. [p39_sycl.hpp](../packet45-merged3/p39_sycl.hpp)
retains the selected low rows4 workgroup, four partials, barrier, ordered
`(p0+p1)+(p2+p3)` and BF16 boundary before `silu_div4`.
The gate's K320 loop has one full 256 tile and only eight active lanes in
the last tile. Inject has just four output rows and is latency/occupancy
limited despite only 163,840 weight bytes per side. The gate and low together
perform 13,107,200 scalar products across both sides; inject adds 81,920.
Low-to-gate is a real dependency through 320 rounded activations, while
inject reads the original stream independently. A low+gate+inject merge needs
an explicit producer barrier and exact BF16 low/activation stores; it cannot
feed unrounded accumulators into gate. Recomputing low for every gate row
would multiply useful work, and a cross-workgroup barrier is unavailable.
Start with vector loads, row scheduling and cooperative inject; preserve
the low/activation NaN behavior qualified by packet45.

**Route:** [route42.hpp](../packet45-merged3/route42.hpp) and
[route42_submit.cpp](../packet45-merged3/route42_submit.cpp) implement four
stages: 32 block maxima, 32 ordered 16-value exponential sums, 512 SG32
ranks, and the top-ten normalization. Each of 16,384 ranking lanes computes
the same 32-chunk denominator in source, then computes its candidate
probability and 16 competing probabilities. That is 262,144 normalized
comparisons plus repeated divisions and denominator trees, before compiler
hoisting. The final output also regenerates a denominator. Cache/share the
*identically computed* denominator and normalized probabilities; keep the
sum tree, deterministic exp, lower-index tie break, top-ten sum tree and
division order. Ranking raw logits/exponentials is not automatically exact:
division rounding can create ties. Preserve descriptors, inactive/error
controls and existing scratch bytes where the complete-state gate observes
them. Early stop once rank reaches ten is integer-only and possible, but
needs device timing to decide whether divergence costs more than it saves.

**GDN QKV:** [p33_candidates.hpp](../packet45-merged3/p33_candidates.hpp)
`dense_lane` and the selected `p33.dense.segment` work at 10240×2560 Q6.
Useful expanded bytes are 32.768 MB, not the 21.504-MB packed GGUF. Each
eight-value tile reads one FP32 scale although a Q6 scale covers 16 values;
each neighboring pair of lanes repeats it. The p48 layout reduces alignment
and metadata overhead but its measured gain was only 1.044x/1.043x and was
not selected for integration. Preserve ten serial tiles and the reduction
tree; try aligned loads or multiple independent rows per workgroup. Changing
to split-K would invalidate the oracle. M=2 can share decode and weight loads
across independent accumulators, but only if the engine actually presents
both rows together; engine-sequential execution must be measured as such.

**Attention output/combine:** the shape is 2560×6144 Q6, already fused by
[p39_fused.hpp](../packet45-merged3/p39_fused.hpp) and
[p39_sycl.hpp](../packet45-merged3/p39_sycl.hpp). Each row computes 24
ordered tiles, rounds the projection to BF16, then updates four stream
values. `combine` recomputes `2*sigmoid(inject/4)` for four inject values in
each of 2560 rows: 10,240 identical-per-stream evaluations in source.
Sharing those exact factors can remove deterministic nonlinear work without
changing the projection or stream arithmetic, provided their original FP32
values, BF16 branch boundary and error/active gating are retained. Loads and
subgroup row grouping are other exact-order candidates. This class is not
QSA attention; packet47's split32 QSA kernel is separate and protected.

## M=2 accounting and qualification limits

The engine uses two changing token rows, not merely a four-row workgroup.
Dense/HC unique weights stay constant at M=2; serial engine calls read them
twice logically. Routed gate/up and down have 10–20 unique expert IDs across
two rows, so M=2 tests must cover identical, shifted partial-overlap and
disjoint selections, not assume perfect reuse. Same-slot reuse is not
cross-slot reuse. Input, outputs, state and control cases remain separate per
token. GDN recurrence must advance token 1 from token 0's rounded state.

M=2 timing is absent from the starting p48b summary. No M=1 doubling or
bandwidth calculation is a measured M=2 result. Packet51 must label whether
its M=2 observation is two sequential engine rows or a joint kernel and
report both timed rows, with exact controls and fresh-owner repeats.

No candidate in this ranking is adopted by source inspection. E1/E2 must
prove byte equality at producer and complete-state boundaries before T1/T2.
The existing and packet49 oracles remain valid only when the registered
arithmetic, rounding boundaries and visible state are unchanged.
