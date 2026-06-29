# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe_forward_shared.custom_op at 16.257960 ms). Runner-up is runtime at 4.548153 ms.

## Endpoint Metrics

- Corrected output tok/s: `83.5811481454597`.
- vLLM decode ms/token: `11.964600633291411`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe_forward_shared.custom_op` max `16.257960` ms, rank skew `0.000000` ms.
- `runtime`: top `gpu_model_runner.bookkeeping_sync` max `4.548153` ms, rank skew `0.000000` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.218302` ms, rank skew `0.000000` ms.

## Top Labels

- `moe_forward_shared.custom_op` (moe): max `16.257960` ms, mean `16.257960` ms, rank skew `0.000000` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `10.785080` ms, mean `10.785080` ms, rank skew `0.000000` ms.
- `gpu_model_runner.forward_total` (runtime): max `6.902923` ms, mean `6.902923` ms, rank skew `0.000000` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.815680` ms, mean `6.815680` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `5.220848` ms, mean `5.220848` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `4.548153` ms, mean `4.548153` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_to_list` (runtime): max `4.497112` ms, mean `4.497112` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `2.368607` ms, mean `2.368607` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.down_proj` (moe): max `1.364524` ms, mean `1.364524` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.720716` ms, mean `0.720716` ms, rank skew `0.000000` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.648984` ms, mean `0.648984` ms, rank skew `0.000000` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.365271` ms, mean `0.365271` ms, rank skew `0.000000` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.218302` ms, mean `0.218302` ms, rank skew `0.000000` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.129734` ms, mean `0.129734` ms, rank skew `0.000000` ms.
- `gpu_model_runner.select_sample_hidden` (logits_sampler): max `0.049562` ms, mean `0.049562` ms, rank skew `0.000000` ms.
- `gpu_model_runner.bookkeeping_invalid_clear` (runtime): max `0.002188` ms, mean `0.002188` ms, rank skew `0.000000` ms.
