# Packet49c decisions and negative-result index

| Finding | Evidence | Revisit condition |
| --- | --- | --- |
| Packet51 expsgate, GDN QKV and HC inject are not winners | [Packet51 measured result](../../../../notes/2026-10-17-own-runtime-packet51-device-result.md) | New separately qualified mechanism |
| HC final low/gate were not selected production classes | [Integration](INTEGRATION.md) | Matched byte and timing evidence |
| Duplicate HC dispatch insertion inside command preparation does not compile | [Correction receipt](evidence/preparation-corrections/receipt.json) | Hook only actual linear dispatch; no blind repeated replacement |
| Attention split4 workspace is device-only intermediate state | [Kernel review](REVIEW-KERNELS.md) | Compare same-backend bytes, exclude only that workspace from canonical cross-backend digest |
| Prepared wrapper hoists launch ranges outside inner scopes | [Compiler refusal](evidence/device-compile-refusal/receipt.json) | Use scope-independent constants in captured launch ranges; preserve geometry |
| HC gate production rows are10240, not the four inject rows | [Integration](INTEGRATION.md) | Keep full10240×320 fixture geometry |
| Copied2.5GB retained build plus both chains exceeds available root space | [Storage budget](ARTIFACT-RETENTION.md) | Measure lean build and enforce650MB final cap; never spend49b allowance |
| Waiting49b queue has no cross-queue launch lock | [Queue review](REVIEW-INDEPENDENT.md) | Coordinator exclusive scheduling; never infer mutual exclusion from chain-local flock |
| STOP does not cancel an already launched window or free a disk reserve | [Switch tests](test_p49c_switch.py), [runbook](WINDOW.md) | Apply only while waiting; active windows retain cooperative teardown contract |

Packet49b's compact expert row pitch, split32 arithmetic identity, prior
SPEED6 rollback conclusions and all inherited negative results remain in
[its unchanged index](../packet49b-gemv/DO-NOT-REPEAT.md).

This preparation is closed in [the evidence-linked closeout](CPU-PREPARATION-CLOSEOUT.md).
Integrated device and model qualification remain the coordinator's next work.
