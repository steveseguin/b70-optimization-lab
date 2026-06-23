# 2026-06-23T2200 - MTP Backend-Sampled Fast Top-K Smoke

## Question

Can llama.cpp's existing backend sampler output path avoid draft MTP's full-vocab
raw-logit host copy/CPU scan and improve valid fresh-response throughput?

This was tested after code inspection confirmed:

- `llama_context::decode()` suppresses full raw logits if every output row has a
  backend sampler;
- backend `top_k` emits compact sampled logits/candidates;
- sampled tensors are copied with `ggml_nbytes(tensor)`, so transfer is compact;
- SYCL/XPU backend top-k supports `k <= 32`.

## Patch

Patch snapshot:

- `patches/gemma4-llamacpp-mtp-backend-sampled-fasttopk-loss-20260623.patch`

Behavior:

- allow `LLAMA_MTP_DRAFT_FAST_TOPK=1` with `MTP_BACKEND_SAMPLING=1`;
- cap backend draft top-k to 32 for SYCL/XPU;
- in `draft_fast_topk_sample()`, prefer
  `llama_get_sampled_logits_ith()` + `llama_get_sampled_candidates_ith()` and
  only fall back to raw `llama_get_logits_ith()` outside backend mode.

The patch was reverted after the smoke because it lost throughput.

## Run

Label:

`gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-backendsampled-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T220022Z`

Summary:

- data: `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-backendsampled-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T220022Z/summary.json`
- server stdout: `data/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-backendsampled-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T220022Z/server.stdout.log`
- external server log: `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-backendsampled-smoke-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-20260623T220022Z.server.log`

Command identity:

- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- GPU count: 1, `ONEAPI_DEVICE_SELECTOR=level_zero:0`
- MTP: draft-mtp, `n_max=7`, `n_min=2`, `p_min=0.12`
- draft model: `mtp-gemma-4-26B-A4B-it.gguf`
- backend sampling: enabled
- `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `LLAMA_MTP_DRAFT_TOP_K=10`
- `--ctx-checkpoints 0`
- canary repeats: 32, bench repeats: 4

## Result

Valid fresh-response result, but **not a record**:

- canary: `128/128` pass;
- mean after TTFT: `88.66255774914706 tok/s`;
- wall mean: `69.41320625896923 tok/s`;
- first request after TTFT: `88.5293730718527 tok/s`.

Best valid fresh-response record at time of test:

- `91.61894213332073 tok/s` after TTFT;
- label:
  `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-repeat-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T150833Z`;
- canary: `384/384`.

Decision: **loss / do not promote / do not submit to LocalMaxxing**.

## Interpretation

The sampled-output bridge works correctly enough for the canary, but the SYCL
backend top-k graph work costs more than the current CPU-side full-vocab scan
and host raw-logit path for this single-session fresh-response workload.

The server profile showed draft decode dominated the run; fast top-k scan/logit
handling was already a small fraction. This makes a generic backend top-k path a
poor tradeoff unless the top-k itself can be made substantially cheaper or
specialized for draft MTP.

Next better lanes:

- CPU cleanup in `common/speculative.cpp`: remove hot `{ seq_id }` temporary
  vectors, direct O(tokens) seq-range discovery, reserve `verify_h`;
- avoid redundant synchronizations around MTP fast sampler access;
- if revisiting compact logits, implement a specialized draft-MTP compact top-k
  graph/output path rather than the generic backend sampler.

