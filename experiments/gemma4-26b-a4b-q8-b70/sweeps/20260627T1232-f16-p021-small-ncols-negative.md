# 2026-06-27T12:32Z - F16 p021 small-ncols KQ specialization

## Idea

The node profile shows KQ attention matmuls shaped like:

- node: `MUL_MAT:kq-0`
- dst: `ne=[256,2,16,1]`
- src0: F16 permuted KV cache, `ne=[256,256,8,1]`
- src1: F32 permuted Q, `ne=[256,2,16,1]`

The existing SYCL dispatch sends this multi-token p021 shape to
`ggml_sycl_mul_mat_batched_sycl`. I added an env-gated experimental path:

- `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`
- one warp computes one `(row, token, q_head)` output for `src1->ne[1]` in
  `2..8`.

This is correctness-preserving but intentionally simple; it is not a tiled
GEMM.

## Result

Paired screen, built from `/home/steve/src/llama.cpp-gemma-record-repro-c926`:

| label | flag | ubatch | fresh row0 tok/s | canary |
| --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-p021-control-ub768-20260627T123234Z` | off | 768 | `104.11352835182656` | pass |
| `gemma4-q8-gpu1-p021-small-ub768-20260627T123234Z` | on | 768 | `95.99940842184174` | pass |
| `gemma4-q8-gpu2-p021-control-ub832-20260627T123234Z` | off | 832 | `103.99765384833461` | pass |
| `gemma4-q8-gpu3-p021-small-ub832-20260627T123234Z` | on | 832 | `96.00163376690254` | pass |

## Decision

Hard negative. The simple warp-per-output kernel is much slower than the
existing batched path. Do not enable `LLAMA_SYCL_F16_P021_SMALL_NCOLS` for
headline runs. A future attention attempt would need a real tiled small-matrix
kernel, not this scalar/vector shortcut.
