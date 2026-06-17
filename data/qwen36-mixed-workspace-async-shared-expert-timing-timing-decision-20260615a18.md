# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.quant_method_total at 4.611344 ms).

## Endpoint Metrics

- Corrected output tok/s: `95.31141643086656`.
- vLLM decode ms/token: `10.492439914742135`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe.quant_method_total` max `4.611344` ms, rank skew `0.470441` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `5.821588` ms, mean `5.593283` ms, rank skew `0.325174` ms.
- `gpu_model_runner.model_forward` (runtime): max `5.767066` ms, mean `5.539623` ms, rank skew `0.323694` ms.
- `moe.quant_method_total` (moe): max `4.611344` ms, mean `4.277015` ms, rank skew `0.470441` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `2.621235` ms, mean `2.277988` ms, rank skew `0.471927` ms.
- `moe.apply` (moe): max `1.592781` ms, mean `1.585026` ms, rank skew `0.020717` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.010014` ms, mean `1.004210` ms, rank skew `0.012759` ms.
- `moe.internal_gate` (moe): max `0.416852` ms, mean `0.411049` ms, rank skew `0.009288` ms.
- `moe.router_select` (moe): max `0.182907` ms, mean `0.178121` ms, rank skew `0.008448` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.175550` ms, mean `0.172259` ms, rank skew `0.005795` ms.
- `xpu_moe.gemm1_w8a8` (moe): max `0.138012` ms, mean `0.136067` ms, rank skew `0.003836` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.130229` ms, mean `0.129118` ms, rank skew `0.002903` ms.
- `xpu_moe.gemm2_w8a8` (moe): max `0.111458` ms, mean `0.110789` ms, rank skew `0.001082` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.063988` ms, mean `0.062394` ms, rank skew `0.002429` ms.
- `xpu_moe.activation` (moe): max `0.056150` ms, mean `0.055327` ms, rank skew `0.001198` ms.
- `xpu_moe.gather` (moe): max `0.055911` ms, mean `0.054922` ms, rank skew `0.001676` ms.
- `xpu_moe.gemm2_quant` (moe): max `0.053141` ms, mean `0.051809` ms, rank skew `0.002334` ms.
- `moe.shared_experts.determine_apply_order` (moe): max `0.022124` ms, mean `0.020071` ms, rank skew `0.003396` ms.
- `moe.shared_experts.determine_sync_order` (moe): max `0.017002` ms, mean `0.015734` ms, rank skew `0.001938` ms.
- `moe.dispatch` (moe): max `0.011299` ms, mean `0.009646` ms, rank skew `0.002880` ms.
- `moe.combine` (moe): max `0.010332` ms, mean `0.008834` ms, rank skew `0.002192` ms.
