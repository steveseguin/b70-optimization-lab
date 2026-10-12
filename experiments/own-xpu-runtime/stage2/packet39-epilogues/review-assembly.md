# Independent assembly review

Reviewed the generated GEN text, not only whole-kernel instruction totals. Each GEMV has a baseline/fused template pair in `candidate-modules.json`; split-four candidates also have separate finish pairs. The review locates backward branches, counts the instructions and UGM messages in the enclosed GEMV loop, and inspects opcode differences. These are static instruction counts, not measured device timings. No device ran.

## Preserved first iteration

The initial modules were `958b6eefad6be96c35e6a7b18addafdc785f0880d98fe1f906f4d092ff8dbca1` (GEMVs) and `2e1394b2dca0c4b367235112b230ac5a03ed58ff8388c1599530982b05195bf4` (finishes). Their source, module and machine-count snapshots remain in `evidence/iteration1/`. Initial expert route voting happened before the GEMV and kept its predicate live across the dot-product loop.

| Chain | Initial loop inspection | Decision |
|---|---|---|
| HC low, split four | GEMV loop unchanged; epilogue added only to existing finish | Loop gate passes |
| Shared up Q6, split four | GEMV loop unchanged; epilogue added only to existing finish | Loop gate passes |
| Attention projection, split four | GEMV loop unchanged; epilogue added only to existing finish | Loop gate passes |
| Shared up Q8, one pass | 113 instructions and 7 UGM messages per static loop in each variant | Loop gate passes |
| Shared down Q8 | Two main packed-weight loop regions each retain 84 instructions and 6 UGM messages | Loop gate passes |
| GDN QKV convolution, Q6 and Q8 | 113 to 114 instructions per GEMV loop; 7 UGM messages unchanged. Opcode multiset difference is exactly one `sync.nop`. | Reject this code-generation form under the requested strict loop gate |
| Paired expert activation | Weight-message count unchanged; predicates spill more often (18/18 stores/loads to 20/22) despite a slightly shorter GEMV body | Initial form rejected pending shorter predicate lifetime |
| Expert down status | Adds 26 predicate stores and 27 predicate loads; baseline has none | Initial form rejected |

The GDN comparison is directly visible in initial GEMV assembly entries 0017/0018 and 0019/0020: the fused loop occupies lines 753–869; baseline lines 408–523. Comparing opcode multisets finds only the additional scheduling no-op. This is not a new floating arithmetic operation or memory message, but it is an extra instruction in the hot loop, so this review does not waive the user's gate.

Predicate spills are register spills into general registers, distinct from UGM scratch-memory traffic. They must still be reported: zero scratch bytes does not establish no new spills. The initial routed candidates fail the conservative no-new-spill condition.

## Second iteration

The source change moves expert all-route voting until after the subgroup GEMV reductions. Down-status does not need an all-route vote at all: each invalid slot's row zero sets sticky error through compare-exchange from 0 to 1, after its unconditional GEMV work. Every output/status remains written; preexisting nonzero sticky errors and inactive execution retain their bytes. No convolution arithmetic or GEMV body was changed to chase its one-instruction regression.

Second-iteration module `1be5c4a97d0e` confirms the down fix: 1,726 to 1,744 static instructions, 58 to 59 static memory messages, no predicate spills in either version and unchanged GEMV loops. The added message is the sticky compare-exchange path. Expert activation still has 20/22 flag stores/loads versus 18/18 and stays rejected. The move did not fix that gate.

## Status-only fallback

The third iteration adds `expert_checks`: identical paired gate/up GEMV outputs and both status buffers, with status checks absorbed into the invalid slot's row-zero epilogue. The separate activation remains scheduled. This avoids the cross-slot activation guard and its long deterministic exponential path. Source review confirms that the two status arrays are the same route-validity predicate and that a CAS from any invalid slot matches their later checks. The two arrays remain independently written and compared.

The IQ2_S status-only form passes the conservative initial assembly gate; the IQ3_S form has an extra instruction in its loop and is retained as a rejected diagnostic. Format mapping is explicit: IQ2_S is enum 22, IQ3_S is enum 21. The rejected full-activation candidate and its status-only fallback are mutually exclusive at a plan site; launch savings must never add both.

## Selected geometry correction

Independent chain review found that the measured HC low and shared-up projections select `p28.dense.rows4`, not the two-launch subgroup-32 split-four form used by the first prototype. Those initial HC/shared assembly comparisons are therefore historical prototype evidence, not admissible selected-plan comparisons. The corrected implementation uses four rows per work-group, WG128 for split one or WG512 for split four, and retains the original 32-float local allocation and unconditional work-group barrier. Split four finishes inside that work-group; no separate finish launch is introduced. Shared-up uses the actual selected p28 dense body. Attention retains its selected subgroup-32 split-four kernel and separate finish.

The final selected-geometry verdict is below. Whole-kernel instruction/message deltas include alternative deterministic-math branches. They are static ISA totals, not executed operation counts or time. A GEMV subgroup maps to one row; the standalone attention finish is a SIMD32 range kernel covering 32 rows. No per-row dynamic counter or speed claim is inferred from those static totals.


## Final verdict

Final modules: `f83ecde6e634a9299103faa0f6ce5adbe4c1a939e24435fe4f233b3fe3aac30d` and `bc3c40a01aa695efafe40855f7a706e29c37ac570c83f5e1ceb421dd485c326f`. The source-bound machine packet contains 32 kernels including original runtime tails and wrapper variants. `review-assembly-details.json` records a separate opcode-histogram audit against the final GEN assembly hashes and exact backward-branch regions.

| Final selected chain | GEMV-loop evidence | Independent verdict |
|---|---|---|
| Expert checks, IQ2_S | Largest region 553 instructions / 22 memory messages in both variants; opcode histograms equal; existing 18/18 predicate spill counts unchanged | Admit to coordinator G4; activation stays separate |
| Expert down status | Three unchanged six-instruction half-conversion loops; unrolled dot-product audit described below | Admit to coordinator G4 |
| HC low activation | Rows4 split-four loop 95 / 6 in both variants; opcode histograms equal | Admit to coordinator G4 |
| Shared up activation Q6 | Actual p28 rows4 split-four loop 95 / 6 in both variants; opcode histograms equal | Admit to coordinator G4 |
| Shared up activation Q8 | Actual p28 rows4 split-one loop 92 / 6 in both variants; opcode histograms equal | Admit to coordinator G4 |
| Attention combine | GEMV remains unchanged, with 95 / 6 loop; only its already-existing standalone finish changes | Admit to coordinator G4 |
| Shared down combine | Both main packed-weight loop regions remain 84 / 6; opcode histograms equal | Admit to coordinator G4 |
| Full expert activation, both formats | New predicate spills remain; IQ2 also gains a loop instruction in the final compilation | Reject selection; retain diagnostic binary |
| Expert checks, IQ3_S | Loop grows 591 to 592 instructions with 22 memory messages unchanged; opcode difference is one `sync.nop` | Reject selection |
| GDN QKV convolution, both formats | Loop grows 113 to 114 instructions; opcode difference is one `sync.nop`; 7 memory messages unchanged | Reject selection |

The unrolled down path was not approved merely because its three small backward loops match. Up to the first BF16 output store, the unchanged dot-product and output-conversion core has exactly 1,696 static instructions in both variants after excluding newly introduced sticky-guard source IDs 1657 and above. Their opcode histograms match exactly. Each core has 90 floating multiply/add instructions and the same complete message histogram: 27 BF16/half loads, 24 byte loads, identical argument/route loads, and the first BF16 output store. The compiler schedules two new integer moves and two comparisons for the sticky guard just before that output store; these belong to the row epilogue, not to weight decoding or accumulation. Total-kernel growth is 18 instructions and one atomic message. Register allocation and instruction scheduling differ, so this proves no added static GEMV work, not a measured runtime improvement.

Every admitted pair remains SIMD32 with 128 GRFs. There is no new scratch-memory allocation or predicate-spill count. HC/shared split four retain the original local storage and work-group synchronization: the disassembler reports the same three barrier-related instructions and four SLM messages for baseline and fused. Shared split one retains the source barrier; the compiler eliminates its unused synchronization/local storage in both variants. No extra reduction was introduced.

The admitted combinations would remove **431 launches per token** if device byte gates and timing qualify them. This is dispatch accounting, not a measured speed result. G4 still includes rejected forms as explicitly rejected diagnostics, and must not use them to construct the selected dispatch. CPU NaN diagnostics and the full-model host gate remain independent of this assembly verdict; an assembly admission is not an all-input identity pass.
