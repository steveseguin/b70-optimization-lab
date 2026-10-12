# Independent attention arithmetic review

Reviewer: packet30 route-family agent, reading attention.hpp, attention.cpp and
attention_cpu.cpp directly against packet27 kernels.hpp and core_v2.hpp.
No device execution was performed. This review did not rely on the author’s
arithmetic conclusion.

The score SG kernel assigns eight adjacent products to each lane. Its three
private tree levels produce the original aligned 8-leaf nodes; the five
subgroup levels produce original levels4–8. This is the same 256-leaf score
sum as Core::dot, not a lane-striped reduction. The score_softmax candidate
instead computes each score’s full 256-leaf tree privately within its owner
lane. Both divide by detmath::sqrt(256.f) only after the original score sum.

For softmax and value, subgroup_tree computes aligned 32-leaf subtrees and
their ordered upper tree. The partial final chunk retains each missing-right
+0 operation through min(global tree height,5), including width33’s five odd
tail additions. No fictitious extra levels are added for global widths below32.
The selected order is maintained; attention is not reordered chronologically.
Max follows the incumbent selected-order std::max scan. Detmath exponentials,
the denominator, F32 probabilities, the value-product tree, inner BF16 cast,
sigmoid multiplication and outer BF16 cast are in the incumbent order.

In the merged stage, owned[chunk] is lane-private. All lanes reach the same
shuffle calls, and the subgroup tree’s j=chunk*32+lane indexes precisely that
lane’s owned element. It never relies on reading freshly written global
scores without a memory barrier. Each score/probability and final output has
one writer; stage event dependencies protect cross-launch reads. No local
memory or subgroup/workgroup barriers occur in the candidate bodies.

The host fixtures compare actual frozen Core outputs, ng incumbent outputs,
candidate outputs, and admitted score/probability intermediates. They test
selected-order reversal, every odd-tree length1..2051, short and full budgets,
required positions, and real qsa_select ties. The maximum partial array65
covers ceil(2051/32). Device argument controls prevent selected IDs outside
capacity/position and admitted bounds before address formation.

Scope qualifications retained in the packet:

- Empty selection intentionally follows the ng/runtime incumbent no-write
  behavior, whereas Core rejects empty attention. The host test explicitly
  records the disagreement; it must never be reported as a three-way pass.
- Runtime selection is a packed prefix followed by -1 sentinels. Core scans
  all non-sentinel IDs while incumbent/candidate stop at the first sentinel.
  A selection with holes is outside that schedule invariant.
- Incumbent score kernels write -Inf to unused score scratch; admitted-only
  candidates leave that unused scratch untouched. G3 compares model output
  and error bytes; host tests additionally compare admitted scratch. This
  scratch difference must be disclosed and is not a semantic model output.
- Nonfinite Q/K attention fixtures have not established Core/incumbent parity;
  the claimed triple agreement is scoped to finite fixtures. Route’s separate
  nonfinite rejection contract is independently tested.

No arithmetic or semantic-output write-race defect found for the registered
finite, packed-prefix decode domain. Device byte parity and speed remain
unmeasured and are required before adoption.
