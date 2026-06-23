# Backend Top-K MTP Losses

Date: 2026-06-23

Goal: test whether llama.cpp's existing backend `ggml_top_k` sampled-logits /
candidate path can beat the current CPU fast-top-k MTP draft path by avoiding
full-vocab host scan/copy.

Common identity:

- runtime: `/home/steve/src/llama.cpp-latest-gemma`, llama.cpp `c926ad098`,
  SYCL AOT BMG build;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft model: `mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  backend sampling enabled, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`,
  `BENCH_PROMPT_MODE=filled-long`, `CANARY_REPEATS=96`,
  `BENCH_REPEATS=8`;
- validation shape: `384/384` chat canary required; benchmark shape is
  `588` prompt tokens / `512` output tokens.

## Existing Backend-Sampling Control

This uses upstream backend top-k sampling, without the extra source patch. It
preserved quality but was much slower than the current record.

| Run | Variant | Canary | tok/s after TTFT | tok/s wall | TTFT ms | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-c926-backendtopk4-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T162500Z` | `top_k=4` | 384/384 | 89.768906 | 70.189247 | 1591.032 | valid loss |
| `gemma4-q8-gpu1-mtp-n7-c926-backendtopk8-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T162500Z` | `top_k=8` | 384/384 | 88.317632 | 69.163422 | 1605.507 | valid loss |
| `gemma4-q8-gpu2-mtp-n7-c926-backendtopk10-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T162500Z` | `top_k=10` | 384/384 | 87.843035 | 68.883698 | 1604.257 | valid loss |
| `gemma4-q8-gpu3-mtp-n7-c926-backendtopk20-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T162500Z` | `top_k=20` | 384/384 | 84.069360 | 66.590128 | 1598.688 | valid loss |

## Source Patch: Compact Backend Top-K Reader

Patch artifact:
`patches/gemma4-llamacpp-mtp-draft-backend-topk-loss-20260623.patch`.

The patch added `LLAMA_MTP_DRAFT_BACKEND_TOPK=1` so MTP would consume
`llama_get_sampled_logits_ith()` and `llama_get_sampled_candidates_ith()`
directly, sort only the returned `k` entries, compute the same local softmax,
and fall back if backend sampled tensors were missing. It compiled and served,
but did not improve speed over the backend-sampling control.

| Run | Variant | Canary | tok/s after TTFT | tok/s wall | TTFT ms | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-c926-backendfasttopk4-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T163738Z` | `top_k=4`, `LLAMA_MTP_DRAFT_BACKEND_TOPK=1` | 384/384 | 89.682396 | 70.100117 | 1594.812 | valid loss |
| `gemma4-q8-gpu1-mtp-n7-c926-backendfasttopk8-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T163738Z` | `top_k=8`, `LLAMA_MTP_DRAFT_BACKEND_TOPK=1` | 384/384 | 88.502988 | 69.304392 | 1602.649 | valid loss |
| `gemma4-q8-gpu2-mtp-n7-c926-backendfasttopk10-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T163738Z` | `top_k=10`, `LLAMA_MTP_DRAFT_BACKEND_TOPK=1` | 384/384 | 87.776293 | 68.848082 | 1603.702 | valid loss |
| `gemma4-q8-gpu3-mtp-n7-c926-backendfasttopk20-ctxcp0-nmin2-pmin012-dthreads32-dtb32-filled-long-deep-20260623T163738Z` | `top_k=20`, `LLAMA_MTP_DRAFT_BACKEND_TOPK=1` | 384/384 | 84.260249 | 66.649731 | 1605.599 | valid loss |

Decision:

- Reject backend top-k transport for this lane. The SYCL `ggml_top_k` graph path
  plus sampled-tensor handling costs more than the current CPU fast top-k scan
  on this B70/Gemma MTP shape.
- Restore source and binary to the approved CPU fast-top-k patch after the
  experiment.
- Do not spend more lanes on backend top-k unless the sampled tensor path is
  fused deeper into the logits op; the standalone backend top-k op is too slow.
