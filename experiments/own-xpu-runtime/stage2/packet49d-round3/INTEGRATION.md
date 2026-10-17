# Packet49d integration

This packet copies packet49c's engine and reads the pinned lab candidates from
[packet54's map](../packet54-compute/INTEGRATION.md) and
[packet53b's map](../packet53b-virtual/INTEGRATION.md). The user authorizes
prebuilding every eligible choice before the device decision. Device admission
still requires the combined 40us trigger in both packet54 timing owners.

| Class | Implementation | Engine site |
| --- | --- | --- |
| Expert gate/up | banked virtual8 split stream | `Engine::linear`, p49b production expert admission |
| Expert down | banked virtual16 | same P39 expert branch |
| Small FFN Q6 | banked virtual4 | small_groups branch, only small.ffn.q6 |
| Route | production / route-rank4 / route-exp32-rank4 | Prepared submit function, four route stages |
| GDN recurrence | production / rows4-shared / rows8-shared | Prepared submit function, same BF16 state in/out |
| HC a/f mix | production / mix-vector4 | Prepared submit function for each separate side |

Production recurrence retains the SPEED6 round2 dispatch. Production route is
packet49c's four-stage path. HC production norm and inject remain unchanged.
Rejected norm/combine candidates and rejected expert alternatives are excluded.

Selection parses once at engine initialization. The same bytes are SHA256-checked
against the seal's expected digest. The target's prepared records hold function
pointers, so per-token replay contains no candidate-name selection branch.
Banked paths are fixed specializations. Prepared command capture uses the same
submitters and checked source transform. M=2 means two serial rows, not a batched
kernel; recurrence row1 reads row0's rounded BF16 state.

Expert validation retains p49b's shape/type/extent/alignment/alias/route/status
checks and P39 sticky controls. It reuses compact 820/360-byte rows with no new
weight bank or repacker. Small FFN keeps packet27 tuple validation, ordered12
bindings and follower skipping. Recurrence and mix preserve live allocation,
input/output/control extent and alias validation. Route scratch, events and
source activation boundaries remain unchanged. HC sides are never fused across
attention or FFN work. No extra persistent GPU buffer is introduced.

The target split 23/25, draft rank 1, capacity 4096, weights, BF16 KV and rollback
rules remain unchanged. DraftRuntime keeps its existing kernels. The full model
uses packet49's existing complete oracle and arithmetic iq3-p49-split32-v1.

CPU gates cover all choices, not just the later selection. K1 repeats the actual
submitter gates in fresh device owners. K2 measures every new choice and both
production controls, and binds its coverage to the selected table. K2 never
substitutes its one-owner timings for the sealed two-owner packet54 decision.
Model and captured replay qualification still require the complete runbook.
No operator timing sum is reported as integrated model throughput.
