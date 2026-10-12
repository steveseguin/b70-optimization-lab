# Independent route arithmetic and write review

Reviewed independently by the attention-family agent, directly reading
`route.hpp`, `route.cpp`, `route_cpu.cpp`, packet27 `adapter.cpp`
(`SimpleNew<Op::route>` and `simple_body` phases 0..4), packet27 `kernels.hpp`,
and `core_v2.hpp` route and expert_gather equations. This review did not adopt
the route author's conclusion as evidence. No device was run.

## Tree identity

At width512, each z in `probabilities` denotes one aligned group of32 original
exp leaves. `chunk_tree` updates lanes0,2,... for distance1, lanes0,4,... for
distance2, then distances4,8,16. Every update has the identical children of
the corresponding original adjacent-tree node. Sixteen chunk roots are
original level-five nodes. The serial tree over those sixteen roots computes
levels six through nine unchanged. The original adapter's 16-leaf chunks
instead stop at level four before reducing32 roots; both evaluate exactly
the same parent-child graph, with the same intermediate float rounding.

For non-power-of-two fixture widths, `d<n` prevents introducing tree levels
that do not exist globally, and `base+lane+d<n ? right : +0` retains each
existing odd-tail +0 addition. The upper tree repeats that same odd-tail rule.
Selected weights use the original top-k-order tree, including top10's tails.
No associative reduction primitive replaces that arithmetic.

## Stable rank and finite handling

`before(x,i,y,j)` is precisely descending float score then ascending index.
For finite route inputs, max-subtracted detmath exponentials and normalization
produce a strict total order when the index breaks probability ties. The
`selected_denominator` repeated argmax therefore enumerates the same prefix
as Core's stable_sort and the incumbent count-of-predecessors rank. Its
previous-value/previous-index predicate excludes exactly the prefix already
selected. It does not remove equal scores with larger indices. Counting
`before(other,k,v,j)` gives each element exactly one unique integer rank.

NaNs and infinities are rejected before exp, matching both runtime and Core;
no output is valid after the sticky error. Subgroup maximum order is harmless
on finite input: it changes no max magnitude. Signed-zero maxima can differ
in sign but subtract/exp yield identical probabilities (exp(+0)=exp(-0)=1).
Descriptors retain expert ID, source row0 and dimensions640/2560. Folded
gather is valid only when consumers use the shared input row as documented.

## Write races and collective convergence

Two-launch stage1 has one subgroup and one lane for each probability cell.
Its event dependency precedes every stage2 reader. Stage2 partitions the
32-element blocks by unique `(workgroup,subgroup)` partition index. Ranking
has a unique rank for every index, so at most one lane writes each selected
output or descriptor. The redundant selected-denominator calculations are
private registers and have no writers to shared storage. WG64 has two
subgroups; surplus partitions do no rank/output work and cannot duplicate a
write. Single-launch finish exchanges probabilities by subgroup selects,
never by a global-memory producer/consumer race. All lanes execute each
shuffle, including lanes whose prospective element is beyond n.
The sticky error accesses are atomic. Inputs/active must remain immutable
for the launch group. Host guards reject overlapping output/scratch spans.

## Findings and disposition

The initial concern about a missing position guard was based on the ng
fixture wrapper, not the actual runtime route path. Re-reading actual
`SimpleNew<Op::route>` confirms it has no position-dependent input or guard;
that concern is withdrawn. Actual runtime `View` also permits F32, unlike
the BF16 ng fixture. Candidate flags8 initially allowed F32 without a matching
CPU fixture. The final route validator now rejects `s.flags!=0`, restricting
this candidate to its registered and tested BF16 input. That finding is
resolved by narrowing scope, with no arithmetic change. No arithmetic or write-race blocker was
found for the registered BF16 512/top10 route.

This is source review and CPU evidence only. It cannot establish GPU lowering,
byte parity on the card, launch representativeness or a performance win.
