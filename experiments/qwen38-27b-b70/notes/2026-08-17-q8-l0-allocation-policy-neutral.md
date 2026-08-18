# Qwen3.8 Q8 Level Zero large-allocation policy

Date: 2026-08-17

Status: closed performance-neutral; do not repeat unchanged

The accepted Level Zero allocator requests only 64-byte alignment and no cache
bias. A same-binary door tested GiB-scale model-rank buffers with
`ZE_DEVICE_MEM_ALLOC_FLAG_BIAS_CACHED`, 2 MiB allocation alignment, or both.
All smaller allocations retained the accepted path, and no tensor bytes,
kernels, arithmetic, KV type, collectives, sampling, or outputs changed.

All three modes announced on both B70s and passed `VERIFY_MISMATCH=0`. The
screen used `p64/n256/r3`, target-only equal TP2, Q8_0, F16 KV,
FlashAttention, `b1024/ub256`, and mirrored order
control-cached-align-both-both-align-cached-control.

| Arm | Process means (tok/s) | Steady mean | Delta vs control |
| --- | --- | ---: | ---: |
| control | `35.253638, 35.244166` | 36.837675 | — |
| cached bias | `35.264131, 35.261486` | 36.853725 | +0.043570% |
| 2 MiB alignment | `35.285523, 35.242416` | 36.841875 | +0.011401% |
| both | `35.238785, 35.284328` | 36.838625 | +0.002579% |

“Steady” excludes each fresh process's deliberately retained cold first
repetition. None of the policies cleared noise, so no endpoint gate was run
and nothing is promoted. Both GPUs remained normal with no new Xe/GuC fault,
reset, timeout, or hang.

- candidate library SHA-256:
  `665f3c5973c5870739a7eeb848d85f6b2b35a332fb6bf29fe69475e0aaa7f964`;
- accepted library restored:
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- raw evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-l0-allocation-policy/`;
- local artifact:
  `/mnt/fast-ai/artifacts/qwen38-q8-l0-allocation-policy-20260817/`.
