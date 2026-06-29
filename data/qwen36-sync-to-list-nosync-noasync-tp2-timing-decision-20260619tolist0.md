# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe_forward_shared.custom_op at 10.672416 ms). Runner-up is runtime at 4.757102 ms.

## Endpoint Metrics

- Corrected output tok/s: `84.5483778018902`.
- vLLM decode ms/token: `11.82977495227533`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe_forward_shared.custom_op` max `10.672416` ms, rank skew `0.000000` ms.
- `runtime`: top `gpu_model_runner.bookkeeping_sync` max `4.757102` ms, rank skew `0.000000` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.208694` ms, rank skew `0.000000` ms.

## Top Labels

- `moe_forward_shared.custom_op` (moe): max `10.672416` ms, mean `10.672416` ms, rank skew `0.000000` ms.
- `gpu_model_runner.forward_total` (runtime): max `6.660699` ms, mean `6.660699` ms, rank skew `0.000000` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.578103` ms, mean `6.578103` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `4.757102` ms, mean `4.757102` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_to_list` (runtime): max `4.709645` ms, mean `4.709645` ms, rank skew `0.000000` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `4.296655` ms, mean `4.296655` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `1.192919` ms, mean `1.192919` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.down_proj` (moe): max `0.958071` ms, mean `0.958071` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.713392` ms, mean `0.713392` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.621054` ms, mean `0.621054` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `0.384038` ms, mean `0.384038` ms, rank skew `0.000000` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.350569` ms, mean `0.350569` ms, rank skew `0.000000` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.208694` ms, mean `0.208694` ms, rank skew `0.000000` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.120914` ms, mean `0.120914` ms, rank skew `0.000000` ms.
- `gpu_model_runner.select_sample_hidden` (logits_sampler): max `0.048355` ms, mean `0.048355` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_invalid_clear` (runtime): max `0.001875` ms, mean `0.001875` ms, rank skew `0.000000` ms.
