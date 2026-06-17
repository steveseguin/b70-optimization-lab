# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.quant_method_total at 4.944401 ms).

## Endpoint Metrics

- Corrected output tok/s: `95.62268148297345`.
- vLLM decode ms/token: `10.458571535309602`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe.quant_method_total` max `4.944401` ms, rank skew `0.604510` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `5.576574` ms, mean `5.530085` ms, rank skew `0.102650` ms.
- `gpu_model_runner.model_forward` (runtime): max `5.521583` ms, mean `5.475732` ms, rank skew `0.100535` ms.
- `moe.quant_method_total` (moe): max `4.944401` ms, mean `4.749384` ms, rank skew `0.604510` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `2.894362` ms, mean `2.742585` ms, rank skew `0.522384` ms.
- `moe.apply` (moe): max `1.641688` ms, mean `1.600905` ms, rank skew `0.075775` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.043770` ms, mean `1.017175` ms, rank skew `0.048421` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.891699` ms, mean `0.724810` ms, rank skew `0.495460` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `0.738478` ms, mean `0.725200` ms, rank skew `0.026063` ms.
- `qwen2_moe.shared.down_proj` (moe): max `0.571099` ms, mean `0.549089` ms, rank skew `0.047952` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.377118` ms, mean `0.372809` ms, rank skew `0.012226` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.180559` ms, mean `0.173994` ms, rank skew `0.012108` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `0.149068` ms, mean `0.146085` ms, rank skew `0.007322` ms.
- `xpu_moe.gemm1_w8a8` (moe): max `0.142996` ms, mean `0.138163` ms, rank skew `0.009805` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.133096` ms, mean `0.131062` ms, rank skew `0.004611` ms.
- `xpu_moe.gemm2_w8a8` (moe): max `0.117711` ms, mean `0.113242` ms, rank skew `0.009857` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.064587` ms, mean `0.063601` ms, rank skew `0.002156` ms.
- `xpu_moe.activation` (moe): max `0.060063` ms, mean `0.057868` ms, rank skew `0.004274` ms.
- `xpu_moe.gather` (moe): max `0.057098` ms, mean `0.055756` ms, rank skew `0.002774` ms.
- `xpu_moe.gemm2_quant` (moe): max `0.055064` ms, mean `0.052894` ms, rank skew `0.003789` ms.
- `moe.shared_experts.determine_apply_order` (moe): max `0.040400` ms, mean `0.039311` ms, rank skew `0.001835` ms.
