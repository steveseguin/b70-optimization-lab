# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (xpu_moe.w8a8_offsets at 0.073370 ms).

## Endpoint Metrics

- Corrected output tok/s: `13.71122183533217`.
- vLLM decode ms/token: `73.00549573483295`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `xpu_moe.w8a8_offsets` max `0.073370` ms, rank skew `0.001381` ms.

## Top Labels

- `xpu_moe.w8a8_offsets` (moe): max `0.073370` ms, mean `0.072387` ms, rank skew `0.001381` ms.
- `xpu_moe.w8a8_middle_layerlet` (moe): max `0.059415` ms, mean `0.057668` ms, rank skew `0.002599` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.019098` ms, mean `0.018816` ms, rank skew `0.000526` ms.
