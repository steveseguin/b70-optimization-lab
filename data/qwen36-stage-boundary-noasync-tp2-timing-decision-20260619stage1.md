# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe_forward_shared.custom_op at 17.611224 ms). Runner-up is runtime at 4.675167 ms.

## Endpoint Metrics

- Corrected output tok/s: `83.80381017433882`.
- vLLM decode ms/token: `11.933920866795233`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe_forward_shared.custom_op` max `17.611224` ms, rank skew `0.000000` ms.
- `runtime`: top `gpu_model_runner.bookkeeping_sync` max `4.675167` ms, rank skew `0.000000` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.213776` ms, rank skew `0.000000` ms.

## Top Labels

- `moe_forward_shared.custom_op` (moe): max `17.611224` ms, mean `17.611224` ms, rank skew `0.000000` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `10.720170` ms, mean `10.720170` ms, rank skew `0.000000` ms.
- `gpu_model_runner.forward_total` (runtime): max `6.778446` ms, mean `6.778446` ms, rank skew `0.000000` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.692245` ms, mean `6.692245` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `5.263379` ms, mean `5.263379` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `4.675167` ms, mean `4.675167` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_to_list` (runtime): max `4.623506` ms, mean `4.623506` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `2.313442` ms, mean `2.313442` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.down_proj` (moe): max `1.343854` ms, mean `1.343854` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.702931` ms, mean `0.702931` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.644821` ms, mean `0.644821` ms, rank skew `0.000000` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.358728` ms, mean `0.358728` ms, rank skew `0.000000` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.213776` ms, mean `0.213776` ms, rank skew `0.000000` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.123674` ms, mean `0.123674` ms, rank skew `0.000000` ms.
- `gpu_model_runner.select_sample_hidden` (logits_sampler): max `0.049150` ms, mean `0.049150` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_invalid_clear` (runtime): max `0.002422` ms, mean `0.002422` ms, rank skew `0.000000` ms.
