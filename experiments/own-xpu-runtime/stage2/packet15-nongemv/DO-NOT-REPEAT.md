# Packet15 closed arms

| Arm | Result | Revisit condition |
| --- | --- | --- |
| Single-work-item non-GEMV interpreter as a performance backend | Recurrence ~1,048.6 ms/site despite one submission; dominated by serial work and scratch copies. Keep only as historical reference. | None for performance; parallel kernels need their own exactness gate. |
| Scalar division → reciprocal multiply in Q normalization/index scaling/norm mean | Still failed the initial 50-case CPU suite; GDN M87 first-output-buffer differences grew from 162 to 190 bytes. Reverted. [Patch](rejected-scalar-reciprocal.patch), [receipt](rejected-scalar-reciprocal.json). | Primitive-level evidence establishing the exact reference operation, followed by unchanged-reference census. |
| Promote initial packet15 candidate after a successful SYCL compile | Closed as a promotion path: 12/72 independent CPU fixtures fail. Compilation is not exactness. [Closeout](CLOSEOUT.md). | All CPU reference bytes and two fresh native windows must pass before timing/integration. |
