# Packet15 closed arms

| Arm | Result | Revisit condition |
| --- | --- | --- |
| Single-work-item non-GEMV interpreter as a performance backend | Recurrence ~1,048.6 ms/site despite one submission; dominated by serial work and scratch copies. Keep as the frozen arithmetic control, including decisive device exactness. | None for performance; parallel kernels need their own exactness gate. |
| Scalar division → reciprocal multiply in Q normalization/index scaling/norm mean | Still failed the initial 50-case CPU suite; GDN M87 first-output-buffer differences grew from 162 to 190 bytes. Reverted. [Patch](rejected-scalar-reciprocal.patch), [receipt](rejected-scalar-reciprocal.json). | Only the expression already specified by unchanged Packet 4 core v1; never rewrite reciprocal arithmetic to chase Torch bytes. |
| Promote initial packet15 candidate after a successful SYCL compile | Closed as a promotion path: 12/72 independent CPU fixtures fail. Compilation is not exactness. [Closeout](CLOSEOUT.md). | Corrected CPU core gate now passes 72/72; two fresh native owners must still pass before timing/integration. |
| gating on the superseded packet1b torch reference | Wrong authority: 60/72 measured the pre-rebase vector-library path. The unchanged Packet 4 core v1 gives 72/72 under both compilers. Original Torch bytes remain diagnostic. [Closeout](CLOSEOUT.md). | Do not reopen as a runtime-v1 gate. A new arithmetic identity would need an explicit decision and regenerated fixtures. |
