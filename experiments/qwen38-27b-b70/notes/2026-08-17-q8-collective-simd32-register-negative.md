# Qwen3.8 Q8 register-retained SIMD32 collective tail

Date: 2026-08-17

Status: closed negative; do not repeat unchanged

The accepted 5,120-element TP2 tail uses one 1,024-work-item SIMD16 workgroup
on each B70. After the RMS reduction it crosses a global workgroup fence and
rereads the activation using the Q8 block mapping. This candidate used a
supported SIMD32 workgroup: each lane retained the same five tid-strided RMS
values, while each subgroup simultaneously owned five complete 32-value Q8
blocks. The first RMS reduction was explicitly partitioned into two logical
SIMD16 halves to preserve the accepted per-thread and XOR-tree order.

The BMG-G31 AOT build succeeded and the default-off door
`GGML_SYCL_COMM_DIRECT_Q8_SG32=1` was live. A `p64/n4` verification smoke was
safe, but all `3,640` memo comparisons differed. The verifier compares the
entire reordered Q8_1 buffer, so this is a hard mechanism failure even though
some differences may be in the auxiliary block-sum half.

The normal `p64/n128/r3` gate then decisively rejected performance:

| Arm | Mean decode |
| --- | ---: |
| same-binary accepted SIMD16 | `36.967270 tok/s` |
| register-retained SIMD32 | `35.832043 tok/s` |
| delta | **`-3.070898%`** |

The removed reread/fence could not offset SIMD32 execution and the additional
lane shuffles. No endpoint or semantic run was warranted. Both GPUs remained
normal with no Xe/GuC fault, reset, timeout, or hang. Accepted source and
library were restored byte-for-byte.

- candidate source SHA-256:
  `31fa16c4f347590f020d30b4228a9920224d626ae7b7a1a1e2c4b33082918e96`;
- candidate library SHA-256:
  `218beeedd9fc1f17e5b75b97d43f03158894c67ec32e48981cfb414ec7e4f0ac`;
- accepted source SHA-256:
  `77c626e177996cd8549a30a8c6c14dcd1ad41cc62fd26889e85877f8f579ad39`;
- accepted library SHA-256:
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- exact compressed increment:
  [`../patches/q8-collective-simd32-register-negative-20260817.diff.gz.b64`](../patches/q8-collective-simd32-register-negative-20260817.diff.gz.b64).
