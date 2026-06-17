# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.shared_experts.apply_no_overlap at 15.326142 ms).

## Endpoint Metrics

- Corrected output tok/s: `94.94709148589685`.
- vLLM decode ms/token: `10.535295336012496`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe.shared_experts.apply_no_overlap` max `15.326142` ms, rank skew `1.933684` ms.

## Top Labels

- `moe.shared_experts.apply_no_overlap` (moe): max `15.326142` ms, mean `14.482309` ms, rank skew `1.933684` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `9.668548` ms, mean `9.336125` ms, rank skew `0.939064` ms.
- `gpu_model_runner.forward_total` (runtime): max `6.799322` ms, mean `6.626397` ms, rank skew `0.293440` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.739683` ms, mean `6.564896` ms, rank skew `0.295403` ms.
- `qwen2_moe.shared.down_proj` (moe): max `1.678501` ms, mean `1.576408` ms, rank skew `0.153839` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `1.663302` ms, mean `1.140723` ms, rank skew `1.104413` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `1.014601` ms, mean `1.003601` ms, rank skew `0.018605` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.858952` ms, mean `0.854028` ms, rank skew `0.014850` ms.
- `moe.shared_experts.determine_apply_order` (moe): max `0.109959` ms, mean `0.105586` ms, rank skew `0.006942` ms.
- `moe.shared_experts.determine_sync_order` (moe): max `0.080727` ms, mean `0.079295` ms, rank skew `0.003509` ms.
