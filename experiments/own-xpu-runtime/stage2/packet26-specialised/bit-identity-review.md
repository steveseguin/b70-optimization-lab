# Independent arithmetic review

The windows subagent reviewed the new kernel bodies against `core_v2.hpp`, the
frozen packet 18 adapter and the original non-GEMV kernels. This was independent
of the kernel author's conclusions. No device ran. No arithmetic difference was
found for the registered valid model shapes, subject to the required compiler,
fixture, oracle and device gates; this review does not certify those future runs.

[The hash-bound review](bit-identity-review.json) records each class and source.
[The symbolic check](identity-tree-tests.json) compares 1,056 ordered addition
expressions at widths around odd tails, tile boundaries and all registered large
widths. Every leaf order and explicit positive-zero addition matches the reference
tree. This is stronger than a numerical tolerance test but still does not replace
compiled-kernel byte comparisons.

| Class | Identity argument |
|---|---|
| route | Finite scan precedes outputs; finite max preserves first equal value. detmath exp -> original adjacent sum -> division -> rank of probabilities, with lower-index tie break -> original selected-probability sum -> division. No raw-logit ranking shortcut. |
| gather | IDs validated before conversion; descriptor fields and repeated-row modulo match. Error is delayed until outputs are initialized. Folded producer emits the same route descriptors; dropped repeated-row storage is not observable by its rewired consumers. |
| attn.combine / ffn.combine + following norm | Round combined value to BF16 before squaring, retain the original combined BF16 output, preserve sigmoid/divide/multiply/add parentheses and gain multiplication. New norm is the complete-subtree reduction followed by original upper nodes. |
| hc norms / standalone norms | Square each original value, sum exact ordered tree, divide by width, add 1e-6, detmath rsqrt, multiply input*inv then gain+unit, finally BF16 put. Registered production shape four streams x2560. |
| gdn.recurrence | Each lane sums four products from +0 then tree32. q/k normalization, decay, prediction, delta and updated state retain operation order. State and output round only at original BF16 writes; sequential token loop reads the previous rounded state. |
| gdn.norm | Width128 square tree and inverse norm unchanged. Multiply by gain before sigmoid gate; no intervening BF16 rounding, then final BF16 output. |
| qsa.prepare | Per-head tree128/256, normalize and round to BF16 before rotary. Rotary uses unchanged BF16 tables and preserves a*c-b*s / b*c+a*s parentheses; final output rounds exactly once. |
| qsa.pool | Four chronological inputs sum from +0, divide by4, BF16 round before norm/rotary. Existing earlier complete pools remain unchanged; only newly complete pools recompute. Append reads previous cache positions or current input exactly as reference. |
| qsa.select | Per-block private tree128, max(0,dot) per head, four-head sum from +0, divide by sqrt128. Rank all finite scores with earlier-block tie break; sentinel fill and trailing tokens preserved. |
| attention / qsa.attention scores | Tree256 product order and division by sqrt256 preserved; absent selection writes negative infinity; invalid IDs flagged before address arithmetic. |
| attention / qsa.attention softmax | Max over original chronological scores, detmath exp subtraction, complete-subtree sums with odd-tail +0 then division. Invalid/tail selection checks precede use. |
| attention / qsa.attention values | For valid selections, original probability*BF16 value leaves, same ordered sum, BF16 round before sigmoid-gate multiply, final BF16 output. Poisoned standalone diagnostic output is explicitly outside byte-parity claim; see finding B2. |
| argmax | Finite data selects lower index on ties by ascending chunk and within-chunk strict comparison. Nonfinite fallback repeats original 128-lane selection order and sets the same error output. |
| streams broadcast | Each output reads the identical source modulo input length and uses the same View get/put conversions. |
| ple.add | Preserves inner BF16(b+c) before adding a, followed by output BF16 conversion; no reassociation. |

The review found and repaired the route reduction private-array bound: the shared
upper routine had 128 slots although the validated diagnostic route shape permits
up to 512 selected experts. Its capacity is now 512. It also found that component
wins could accidentally enable an unmeasured folded pair. Folded pairs now have
separate dispatch entries and actual paired K1/K2 fixtures. The argmax fixture's
missing error output was repaired after the independent reference evaluator
exposed it; neither a crash nor an incomplete fixture counts as a passing gate.

One diagnostic limitation is explicit: standalone attention-value calls with
poisoned selection IDs can leave different failed-output bytes. The original
kernel sets a shared error flag while workgroups take independent guard snapshots,
so those failed bytes already depend on workgroup order. The new kernel rejects
invalid addresses earlier. This is not a claim of byte parity for poisoned
standalone diagnostic output. The unchanged model never consumes such a failed
result; valid selections, sticky error, bounds safety and NaN-route byte parity
remain required. No tolerance is introduced anywhere.

The folded route fixture compares retained IDs, probabilities and route descriptors;
the repeated row is deliberately removed from its observable producer outputs.
The all-new real-model oracle gate must verify downstream consumers reading the
single original row, including all 384 retained layer fixtures and eight tokens.

## Named GEMV bridge review

The late `p25_bridge.cpp` addition was independently reviewed against the retained
arithmetic helper and packet 25 candidate bodies. Type and candidate are template
constants. Per-lane products and additions, adjacent subgroup tree32, and split4
`(p0+p1)+(p2+p3)` retain the original arithmetic order. `rows4` changes workgroup
packing; the other named candidates change how the same inputs are loaded or
decoded. Every requested candidate still needs exact finite fixture
checks (nonfinite GEMV inputs remain unqualified; see NONFINITE-GEMV.md). No candidate is accepted merely because this review found no reordered sum.

Two bridge defects were fixed: a routed matrix with count 1 was incorrectly treated
as dense, and paired matrices could have different expert counts or inputs despite
sharing the first matrix's addressing. `has_routes` now distinguishes routing from
count; paired inputs/experts must agree, unsupported row span is refused, and zero
or out-of-range geometry fails before launch.

The bridge has no new write race: every row/projection/split owns its partial;
all participating subgroups write before the workgroup barrier; lane0 of part0
alone writes the final row. Only row0 writes a route status. Route validity is
uniform within a subgroup, so collective loads/reductions are not divergent.
The captured `Bound` is by value. Its pointers refer to weights, input/output and
route/status tensor data. There is no parameter-pointer block, operation list,
format switch inside the device body, or descriptor interpreter. Unsupported
`half_table` and `staged` names are rejected by the bridge.
