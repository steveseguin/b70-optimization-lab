# Do not repeat — packet33 CPU code generation

| Arm/method | Outcome / evidence | Reopen only when |
|---|---|---|
| Source table removal alone | Initial bank still11 messages/octet; final explicit complete vec8 tiles reach7. [review](review-candidate-assembly.md), [patch](iteration1.patch) | A different lowering is verified in GEN |
| Balanced IQ4 select | Divergent branches;17 messages/octet and290–482 instructions. Retained as negative timing diagnostic | Final assembly changes materially |
| Static instruction count as speed | Whole-kernel fitR²0.938, held-outR²-0.246. [model](model.json) | Dynamic path/occupancy/cache information and held-out improvement |
| Synthetic71us as an expert-down forecast | Different code, scale/format/launch traffic and no target-output gate. [measurements](model-notes.md) | Exact kernel/workload/quality identities match |
| Counting all IGC asm files as launched kernels | Retry attempts can share a kernel name; final binary text must select the attempt | Binary-text match is checked |
| A32 by dropping >4GB default | Not runtime-equivalent target options. [options](runtime-options.md) | Runtime legitimately has a qualified matching option |
| Generic activation kernel as launch floor | Shared runtime switch includes QSA/GDN and more; aggregate static prologue is not launch latency | Path-specific dynamic analysis and matched tiny-kernel receipt |
| Changing SG32 to16 as a harmless flag | Changes the lane/tree contract; no candidate accepted | Exact32-lane operation tree and gates preserved |

No packet25–32 source, result, or dispatch was edited. No device ran.
