# Qwen3.8 Flash-Next FP8 512-expert top-k workspace screen

Date: 2026-08-30
Status: lossless component positive; below endpoint threshold

The XPU top-k wrapper allocated an FP32 `[M,512]` scoring workspace even though
the specialized 512-expert kernel reads the router scores directly. A
default-off patch skips that tensor only when
`VLLM_XPU_TOPK_512_SKIP_UNUSED_WORKSPACE=1`; all scoring, selection, and output
code is unchanged.

Three control/candidate/control brackets used fresh processes and hidden seeds
at the production M1, 512-expert, top-10 BF16 shape. Candidate weights, expert
IDs, and source rows matched their controls exactly across 100 hash repeats per
process. Synchronized median reductions were 9.12%, 8.62%, and 7.19%; host
submission medians fell 18.07--20.98%.

Qwen uses this softmax route. Because the source treatment also reaches the
analogous sigmoid wrapper, a separate short control/candidate/control guard
exercised that route too. All three processes produced one identical output
tuple across 20 repeats. Its small timing sample is intentionally not used as
performance evidence.

This is not an endpoint candidate by itself. At 48 calls per target token, the
median synchronized saving projects to only 0.1426 ms/token, or about 0.079% of
the protected 5.5158 tok/s lane if every microsecond transfers. Keep the patch
default-off and do not spend a full model load on it alone. It may be bundled
later only after a larger independently qualified treatment justifies an
endpoint arm.

Evidence:

- structured result:
  [`20260830-topk-512-workspace-component-positive.json`](../data/20260830-topk-512-workspace-component-positive.json);
- benchmark:
  [`benchmark-topk-512-workspace.py`](../tools/benchmark-topk-512-workspace.py);
- source patch:
  [`0006-perf-moe-skip-unused-512-expert-top-k-workspace.patch`](../../../patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0006-perf-moe-skip-unused-512-expert-top-k-workspace.patch).
