# Fast Top-K VMM/UBatch Interaction

Date: 2026-06-23

Goal: test whether the current approved fast-top-k MTP recipe combines with the
earlier VMM-off / larger-ubatch latency lane to beat the `91.618942 tok/s`
LocalMaxxing record.

Common identity:

- runtime: `/home/steve/src/llama.cpp-latest-gemma`, llama.cpp `c926ad098`,
  SYCL AOT BMG build;
- source: approved `common/speculative.cpp` fast top-k patch only;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft model: `mtp-gemma-4-26B-A4B-it.gguf`;
- flags: `MTP_N_MAX=7`, `MTP_N_MIN=2`, `MTP_P_MIN=0.12`,
  `MTP_BACKEND_SAMPLING=0`, `MTP_DRAFT_THREADS=32`,
  `MTP_DRAFT_THREADS_BATCH=32`, `MTP_EXTRA_ARGS='--ctx-checkpoints 0'`,
  `LLAMA_MTP_DRAFT_FAST_TOPK=1`, `BENCH_PROMPT_MODE=filled-long`,
  `CANARY_REPEATS=96`, `BENCH_REPEATS=8`;
- validation shape: `384/384` chat canary required; benchmark shape is
  `588` prompt tokens / `512` output tokens.

Results:

| Run | Variant | Canary | tok/s after TTFT | tok/s wall | TTFT ms | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n7-c926-fasttopk10-vmm0-ub64-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T161751Z` | `top_k=10`, `UBATCH_SIZE=64`, `GGML_SYCL_ENABLE_VMM=0` | 384/384 | 91.158489 | 70.894659 | 1605.478 | valid, below record |
| `gemma4-q8-gpu1-mtp-n7-c926-fasttopk10-vmm0-ub256-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T161751Z` | `top_k=10`, `UBATCH_SIZE=256`, `GGML_SYCL_ENABLE_VMM=0` | 384/384 | 90.992138 | 80.216734 | 757.850 | valid, below record |
| `gemma4-q8-gpu2-mtp-n7-c926-fasttopk10-vmm0-ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T161751Z` | `top_k=10`, `UBATCH_SIZE=512`, `GGML_SYCL_ENABLE_VMM=0` | 384/384 | 91.581388 | 82.292136 | 631.803 | valid, `0.037554 tok/s` below record; keep as best wall/TTFT reference |
| `gemma4-q8-gpu3-mtp-n7-c926-fasttopk8-vmm0-ub512-ctxcp0-nmin2-pmin012-nobs-dthreads32-dtb32-filled-long-deep-20260623T161751Z` | `top_k=8`, `UBATCH_SIZE=512`, `GGML_SYCL_ENABLE_VMM=0` | 384/384 | 90.714535 | 81.580461 | 633.817 | valid, below record |

Decision:

- Do not submit to LocalMaxxing; no run beat the `91.618942 tok/s` record.
- Preserve `VMM=0 + UBATCH_SIZE=512` as a latency/total-throughput reference:
  after-TTFT decode missed the record narrowly, but wall throughput and TTFT
  were much better than the approved record.
- The env identity now records `GGML_SYCL_ENABLE_VMM` in both server logs and
  summary JSON, because this flag is material to comparing these runs.
- Next source-level target: use llama.cpp's existing backend `ggml_top_k`
  sampled-logits/candidates path directly for MTP, sorting only the returned
  `k` entries on CPU, instead of copying/scanning full vocab logits.
