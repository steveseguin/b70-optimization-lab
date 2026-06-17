# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (xpu_moe.w8a8_offsets at 0.099079 ms).

## Endpoint Metrics

- Corrected output tok/s: `13.252894471089892`.
- vLLM decode ms/token: `75.47515074838884`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `xpu_moe.w8a8_offsets` max `0.099079` ms, rank skew `0.004387` ms.

## Top Labels

- `xpu_moe.w8a8_offsets` (moe): max `0.099079` ms, mean `0.095973` ms, rank skew `0.004387` ms.
- `xpu_moe.w8a8_middle_layerlet` (moe): max `0.060602` ms, mean `0.059367` ms, rank skew `0.002749` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.027884` ms, mean `0.027227` ms, rank skew `0.001023` ms.
