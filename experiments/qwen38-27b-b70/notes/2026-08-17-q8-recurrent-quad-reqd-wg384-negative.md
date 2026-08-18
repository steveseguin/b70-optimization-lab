# Qwen3.8 Q8 recurrent-quad required WG384 contract

Date: 2026-08-17

Status: **closed negative; do not promote**

The accepted recurrent GDN quad uses 24 SG16 subgroups, or 384 work-items,
per workgroup. A default-off same-binary specialization added
`sycl::reqd_work_group_size(1, 1, 384)` to that exact Qwen3.8 shape so IGC
could compile with the launch population known. The control remained a
separate unchanged kernel. Model math, row mapping, DP4A/FP32 order, F16 KV,
equal TP2, and every accepted fusion were unchanged.

Candidate library SHA-256 was
`69e36c2ea970c4bf1f8d25791a73efb75eaa694e5a81a8290c7bb2c8fb215187`;
control was
`e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`.
The bounded `p64/n1` smoke completed on both B70s with all 192 recurrent-quad
hits and `VERIFY_MISMATCH=0`.

The decisive same-binary `p64/n512/r3` A-B-B-A bracket measured:

- control: `36.930385`, `36.805976` process means; pooled `36.868181 tok/s`;
- required-WG384: `36.842341`, `36.813402`; pooled `36.827872 tok/s`;
- delta: **`-0.109%`**.

Both treatment positions were below their matched controls, so no endpoint
run was warranted. The older pre-SG24 fixed-WG128 experiment was endpoint-null;
this result closes the distinct compile-time contract for the promoted SG24
geometry. The accepted source and deployed library were restored exactly.
Raw logs are under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-quad-reqd-wg384`;
binary artifacts are under
`/mnt/fast-ai/artifacts/qwen38-q8-quad-reqd-wg384-20260817`.
The retained zero-context patch applies with `git apply --unidiff-zero`.
