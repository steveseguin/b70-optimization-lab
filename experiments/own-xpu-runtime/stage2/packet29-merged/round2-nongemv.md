# Packet 27 non-GEMV designs and identity argument

CPU-only development. No device has run this packet. Times below are hypotheses,
not predictions certified by measurements and not speed claims. K2 must retain
packet 26's measured incumbent unless every compared output byte is identical and
the new median is below 90% of that incumbent in the same run.

| Class / dispatch | Measured incumbent given by coordinator | New design | Hypothesis |
| --- | --- | --- | --- |
| route and route+gather / round2 | about 68 us | Three submissions: cooperative softmax, distributed rank with early exit for losing entries, normalize selected ten | 20–25 us |
| qsa.attention / round2 | about 264 us per layer | Three compile-time score/softmax/value kernels; one 32-thread group per score/value and one per softmax head | 100–120 us |
| gdn.recurrence / round2 | about 53 us; packet 26 new arm about 156 us | One subgroup owns each of 6,144 state rows; four state values per logical lane in private registers; explicit shuffle tree | 30–35 us |
| qsa.select / round2 | about 68 us | Two submissions: one cooperative 32-thread group per pooled block score, then independently ranked blocks and disjoint suffix writers | 25–30 us |
| argmax / round2 | about 297 us in full decode (191 us in K2) | Parallel 1,024-logit chunk winners, followed by chunk-winner reduction | 40–60 us |

## Route

Packet 26's specialised path uses five launches with small maxima and denominator
stages; ranking traverses all 512 probabilities per expert. The new first launch
computes exactly the original finite maximum, exponentials, adjacent denominator
tree and rounded float probabilities in one group. It does not rank raw logits:
softmax rounding can tie values that had different logits. The second launch gives
32 experts to each group. Each entry counts the exact old predicate `other > mine ||
(other == mine && other_id < mine_id)` and stops at rank ten. Such an entry cannot
be selected, so no losing rank is consumed. Winning ranks are unique. The third
launch reduces selected probabilities with the original adjacent tree and stores
the original normalization. Expert ID and descriptor outputs have one writer.
There is no full sort and no global barrier inside a submission.

A folded route has already-available router logits. Its input vector is already
available too; the packet 26 folded schedule keeps the original vector binding for
the expert GEMV rather than copying repeated vectors. Both K2 arms use that same
folded ABI and schedule. The standalone route is also measured independently.

## GDN recurrence

The failed packet 26 arm serializes 128 state values, both dot products and their
32-lane reductions inside one work item. It also launches a separate normalization
stage. It trades an old 32-thread cooperative state row for large private arrays
and long serial dependence chains. The new candidate starts from the old row
ownership: one subgroup per `(value_head, output_row)`.

Lane `l` retains the four products `4*l + {0,1,2,3}` in their old order. Every dot
starts from positive zero and makes four explicit multiply-then-add operations.
The shuffle reduction updates only lanes divisible by twice the stride, for
strides 1,2,4,8,16, exactly the old 32-leaf adjacent tree. This removes the SLM
scratch and workgroup barriers, not arithmetic nodes. Query and key normalization,
softplus branch, decay, delta, state update and output gating retain their original
rounding points. State writes round BF16, and the next token rereads those BF16
bytes. The subgroup barrier before that reread is retained. Distinct subgroups own
disjoint state rows and output elements. Flags retain both registered head layouts.

## QSA selection

The old single-group path performs every block's four 128-element dot products
serially; the packet 26 item path embeds four private trees in every block item.
The new score stage allocates an independent subgroup to each block and uses the
original adjacent 128-product trees. The four head scores still add in order from
zero, followed by the same division. The ranking launch retains stable ID ties.
The selected prefix, trailing unpooled tokens and -1 suffix have disjoint owners;
there is no initialization-versus-ranking race. If any score is nonfinite, only
block zero initializes the entire output to -1 and sets the sticky error.

## QSA attention

The old 128-thread score/value groups exceed the short-context useful parallelism;
packet 26's private score tree trades those groups for serial arrays. This candidate
uses exactly one subgroup per score or output dimension, preserving the product
indices and adjacent tree. Softmax's maximum is computed once per head rather than
repeated by every lane. Maxima/exponentials/denominator/probability/output BF16 gates
and sigmoid remain unchanged. The exact three-stage dependency chain is retained;
there is no approximation, compressed cache, tile reassociation or fused softmax.
All scratch is per workgroup and all output ownership is per head/slot or dimension.

## Argmax

A first stage reduces 1,024-logit chunks across 32 lanes and writes one index and
one nonfinite flag per chunk. The second reduces those winners. Finite comparisons
use greatest value, then smallest original ID; no numeric reduction or rounding
is introduced. Each logit is decoded at its original precision. The nonfinite
slow path deliberately repeats the old 128-lane traversal and tie behavior before
setting the sticky error, so exceptional fixtures preserve the output as well.
Only one work item writes each chunk result and the final output. Index values
remain exactly representable as float within the registered size bound.

## K2 pool workload repair

K2 changed the one-token pool fixture's position to 63 but left prior pooled-cache
bytes from the old position. The frozen reference core recomputes all complete
pools; both native implementations intentionally retain completed pools. The stale
history therefore made both correct implementations differ at slot 7. The repaired
workload computes a reference over the same raw history and seeds only the already
completed pooled prefix (blocks 0–14). Block 15, completed by the current position
63 input, remains untouched and must be calculated by each measured kernel. This
repair changes fixture coherence, not the reference arithmetic or either kernel.
The same moved fixture is added to normal K1 as a CPU-executed regression.

## Validation boundary

`round2::submit` validates shapes and every allocation extent before submitting.
`submit_simple` validates supported input/output types, actual logical output
extents and control/scratch extents. Source format is a template argument;
`Spec`, descriptor tables and `View` type switches do not reach a device loop.
The dispatch enum is interpreted only on the host. Full model kernels have fixed
GDN/QSA dimensions; route 512/top10 is an explicit compile-time instantiation.
Smaller route geometry is a fixture compatibility instantiation, not a model path.

Fixtures compare all affected output buffers, not only token IDs. K1 tests the
new path against both packet 18 and the frozen reference core; K2 compares against
the packet 26 measured selection. Native timing and exactness remain coordinator
work and are required before any promotion.
