# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (xpu_moe.w8a8_middle_layerlet at 0.049362 ms).

## Endpoint Metrics

- Corrected output tok/s: `14.20562843236303`.
- vLLM decode ms/token: `70.40956260607345`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `xpu_moe.w8a8_middle_layerlet` max `0.049362` ms, rank skew `0.001826` ms.

## Top Labels

- `xpu_moe.w8a8_middle_layerlet` (moe): max `0.049362` ms, mean `0.048518` ms, rank skew `0.001826` ms.
- `xpu_moe.w8a8_offsets` (moe): max `0.022380` ms, mean `0.022191` ms, rank skew `0.000359` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.014299` ms, mean `0.014143` ms, rank skew `0.000546` ms.
- `xpu_moe.w8a8_offsets_prefix_op` (moe): max `0.013010` ms, mean `0.012866` ms, rank skew `0.000422` ms.
