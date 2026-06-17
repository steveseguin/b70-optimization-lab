# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.quant_method_total at 4.546182 ms).

## Endpoint Metrics

- Corrected output tok/s: `95.36918771172773`.
- vLLM decode ms/token: `10.487529202691803`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe.quant_method_total` max `4.546182` ms, rank skew `0.467278` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `5.809683` ms, mean `5.617526` ms, rank skew `0.281613` ms.
- `gpu_model_runner.model_forward` (runtime): max `5.751987` ms, mean `5.561547` ms, rank skew `0.278175` ms.
- `moe.quant_method_total` (moe): max `4.546182` ms, mean `4.335170` ms, rank skew `0.467278` ms.
- `moe.apply` (moe): max `1.637274` ms, mean `1.616258` ms, rank skew `0.065783` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.042166` ms, mean `1.029666` ms, rank skew `0.042115` ms.
- `moe.internal_gate` (moe): max `0.423266` ms, mean `0.414783` ms, rank skew `0.018194` ms.
- `moe.router_select` (moe): max `0.184219` ms, mean `0.179279` ms, rank skew `0.010546` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.175215` ms, mean `0.172285` ms, rank skew `0.006879` ms.
- `xpu_moe.gemm1_w8a8` (moe): max `0.141200` ms, mean `0.138628` ms, rank skew `0.007840` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.132426` ms, mean `0.130588` ms, rank skew `0.003687` ms.
- `xpu_moe.gemm2_w8a8` (moe): max `0.114313` ms, mean `0.112891` ms, rank skew `0.005064` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.064335` ms, mean `0.063148` ms, rank skew `0.002761` ms.
- `xpu_moe.activation` (moe): max `0.058727` ms, mean `0.057291` ms, rank skew `0.003199` ms.
- `xpu_moe.gather` (moe): max `0.058577` ms, mean `0.056936` ms, rank skew `0.003076` ms.
- `xpu_moe.gemm2_quant` (moe): max `0.054122` ms, mean `0.053122` ms, rank skew `0.002658` ms.
- `moe.combine` (moe): max `0.008926` ms, mean `0.008740` ms, rank skew `0.000397` ms.
- `moe.dispatch` (moe): max `0.008570` ms, mean `0.008515` ms, rank skew `0.000115` ms.
