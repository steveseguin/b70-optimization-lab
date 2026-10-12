# Route: exact trees with fewer launch boundaries

No device was run for packet30. All times below are hypotheses to test in G3.

## Incumbent cost and a correction

The premise “four-stage incumbent” does not match the actual runtime code:
`packet27-round2/adapter.cpp::simple_new_submit<Op::route,512,10>` issues
**five** phases, 0 through 4. The class receipt independently reports five
launches per route group (15120 / 3024). G3 must reproduce that runtime path,
including folded descriptor outputs, rather than time `ng::route_gather`.
The latter is a fixture-level, single-workgroup implementation and is not the
in-model incumbent. Packet27 K2 reported about 67.3 us for the old route and
84.3 us for the three-launch candidate; W2C reported about 69 us in model.
These different settings do not establish a per-instruction timing breakdown.

The incumbent submits 32 / 32 / 512 / 512 / 1 logical work-items in five
`range` kernels. Their physical workgroup sizes are compiler-selected, not
specified in the source. Phase0 scans sixteen logits per item for maximum
and finiteness. Phase1 rereads all 32 partial maxima in each of its 32 items,
then calculates sixteen detmath exponentials and the adjacent 16-leaf subtree.
Phase2 redundantly calculates the 32-partial upper sum in all 512 items and
divides one exponential. Phase3 performs 512 stable comparisons per item,
262144 comparisons altogether, and writes selected IDs/weights/descriptors.
Phase4 has one item for the ten-value tree and divisions. It has no barriers
or local allocation in those kernels. Five launch floors alone are roughly
17–25 us under the supplied 3.4–5 us/launch observation. The rest includes
serial private work, repeated denominator work, ranking and dispatch overhead;
source inspection cannot assign the remaining microseconds individually.

The round2 candidate submits 1 / 16 / 1 workgroups, all SG32, and allocates
514 floats (2056 bytes) of local memory in every stage, even stages that need
less. Stage0 starts with two control barriers, then has the finite-scan barrier,
a max-consumption barrier, exponential barrier, nine denominator-tree barriers
and a final denominator barrier: **15 barriers**. Only lane0 scans all 512
logits for max/finiteness; each lane evaluates sixteen exponentials. Stage1
has two control barriers per workgroup, then each lane ranks one candidate
with the original predicate and early exit after ten outrankers. Stage2 has
two control barriers, one selected-load barrier, four tree barriers, and one
final barrier: **8 barriers**. These serial steps and local-memory barriers
can cost more than the two saved launches. The measured slowdown is the
reason this packet does not equate fewer launches with an achieved speedup.

## Candidate schedule

`p30.route.two.g1.wg32`: stage1 is one SG32 workgroup. Each lane owns sixteen
aligned-block leaves, finite/max uses subgroup shuffles, then detmath exp,
exact subtree reductions, lane0 upper reduction, divisions and 512 probability
stores. Stage2 is one SG32, reading all probabilities, reconstructing top ten
locally, ranking all 512 elements by counting, normalizing, writing descriptors.
Hypothesis: 20–65 us. The 8192 rank comparisons per lane are the main risk.

`p30.route.two.g16.wg32`: the same first launch; stage2 has sixteen SG32
workgroups, each ranks 32 elements (512 comparisons per lane). Every subgroup
independently reconstructs the ten selected probabilities using ten stable
max selections over its distributed 512 input probabilities. This deliberately
duplicates that small selection task: no workgroup reads another workgroup's
selected-output writes. Hypothesis: 18–50 us; duplicate selection and sparse
output work may erase the gain.

`p30.route.two.g16.wg64`: sixteen WG64 workgroups, two subgroups each, same
algorithm. Each subgroup owns a disjoint candidate block. At width512, sixteen
of the thirty-two subgroups have no rank output block, but all perform the
independent selected denominator calculation. This explicitly measures the
cost of the larger launch geometry. Hypothesis: 20–65 us.

`p30.route.single.sg32`: one SG32 launch retains the normalized probabilities
in sixteen private registers per lane. Rank counting fetches other leaves
with uniform `select_from_group` calls. No global-memory rendezvous is needed:
a second pass over freshly written global memory without a barrier would be
an invalid substitute. Hypothesis: 25–90 us, because the saved launch competes
with many register shuffles and low occupancy.

All candidates have **zero barriers and zero local-memory declarations**.
There is no speculative global-memory visibility assumption. The only global
cross-workgroup dependency is the explicit event edge between two launches.

## Tree and tie identity

For the original 512-leaf adjacent tree, block b owns leaves [32b,32b+31].
At subgroup stride d=1,2,4,8,16, lane i divisible by 2d computes original
node (start=32b+i,width=2d) as its left node plus the lane i+d right node.
The shuffle reads the old level before any lane updates its private value.
Lane0 therefore holds exactly original level5 node (32b,32), not a lane-striped
sum. The sixteen block results remain in block order. Lane0 reduces them at
strides 1,2,4,8, computing original levels6,7,8,9. No additions are reassociated.

Odd diagnostic lengths retain `left + 0.f` at every missing-right original
node, and do not add levels beyond the original global tree height. In a final
partial block, the loop bound is `d<n`, not `d<count`; e.g. width33 requires
five +0 additions to leaf32 before its level6 combination. The ten selected
probabilities use the identical odd-tail adjacent tree before division.

Rank is computed from **normalized F32 probabilities**, not logits or raw
exponentials. The predicate is `p[k] > p[j] || (p[k] == p[j] && k < j)`.
Finite logits imply finite, nonnegative probabilities and a positive sum.
This is a strict total order including rounding ties, so every rank has one
writer. The denominator's repeated maximum selections use exactly that order,
therefore recover precisely ranks0..9. Its values are divided by the selected
denominator at the same F32 rounding point as the incumbent.

The incumbent rejects any nonfinite logit, including NaN, +Inf and -Inf;
it does not propagate NaNs through max. The subgroup OR of finite failures
implements exactly that rejection, with one atomic sticky-error writer and
no output writes. Max reorderings apply only to admitted finite logits.
Signed-zero max choice cannot alter exp(x-max), whose zero result is exp(0)=1.
Inactive and prefailed invocations leave every semantic output unchanged.

Gather is folded: descriptors retain `(expert,0,640)` / `(expert,0,2560)`;
consumers must bind the one 2560-element input row and use row zero rather
than a ten-row materialized tensor. The missing repeated-row buffer is not
an output to compare once those consumers are rewired.

## Host validation and coverage

`validate` checks every used pointer, extent, four-byte alignment, all pairwise
aliases (including scratch/control), registered geometry, BF16 input mode,
and variant. Runtime adapters must invoke it before calling `submit`; USM
ownership/device association must additionally be checked by their arena.
The source statically guards the by-value Capture against the 1024-byte limit.
CPU fixtures cover widths1,3,7,10,17,31,32,33,63,87,127,255,256,511,512;
varied values, complete ties, repeated scores, signed zero, NaN rejection,
infinite rejection, and inactive invocations, across all four variants.
They compare IDs/probabilities/descriptors against `ng::cpu`; the frozen
`core_v2.hpp::Core::run(Op::route)` independently supplies IDs/probability
bytes and failure. Additional guards exercise short outputs/scratch, aliases,
unsupported geometry and unknown variant. These host checks do not replace
G3 device byte comparisons or a fresh device timing result.
