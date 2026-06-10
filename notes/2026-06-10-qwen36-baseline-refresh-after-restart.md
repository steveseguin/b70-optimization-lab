# Qwen3.6 INT8 Baseline Refresh After Restart

Date: 2026-06-10

## Context

After the local fused-kernel diagnostics caused a later `UR_RESULT_ERROR_DEVICE_LOST`
and the accepted TP4 backend was relaunched, I reran the normal single-user decode
benchmark against the restored production-candidate service.

This is a baseline refresh only. It does not change the promoted recipe.

## Recipe Under Test

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Runtime: vLLM XPU TP4, BF16 runtime dtype
- Context: 32K
- Graph: XPU PIECEWISE graph capture
- Collectives: clone-safe custom-op all-reduce
- Endpoint: `http://127.0.0.1:18080`
- Shape: p512/n512 streaming, four measured repeats

## Result

- Output tok/s after first chunk: `94.3105`
- Corrected output tok/s after first chunk: `94.1263`
- Output tok/s end-to-end: `93.0006`
- Total tok/s end-to-end: `186.0012`
- Mean client TTFT: `76.4636 ms`
- Mean vLLM TTFT metric: `75.2096 ms`

## Conclusion

The relaunched accepted baseline is healthy and within noise of the previous
promoted p512/n512 single-request result (`94.52` after-first / `93.21` e2e).
This confirms the restart did not materially change the single-user baseline.

The result is still far below the `>200` single-session decode target, so the
next work should continue on real decode-path bottlenecks rather than service
recovery:

- dense RMS/quant/GEMM boundaries,
- exact MoE epilogue or scratch reuse only if full-model speed improves,
- graph/custom-op boundary reduction,
- runtime config tests that do not change model quality.

## Artifacts

- `data/qwen36-quark-int8-graph32k-single-refresh-20260610.json`
