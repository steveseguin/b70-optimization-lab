# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `scheduler_runtime_static_c1_lane`.
- Leading family: `runtime`.
- Decision basis: `aggregate_exit_summary`.
- Reason: runtime has the largest visible per-family label (gpu_model_runner.draft_total at 79.249109 ms). Runner-up is gdn at 49.206947 ms.

## Endpoint Metrics

- Corrected output tok/s: `0.3403530925281741`.
- vLLM decode ms/token: `3359.38356812494`.
- TTFT ms: `None`.

## Family Ranking

- `runtime`: top `gpu_model_runner.draft_total` max `79.249109` ms, rank skew `0.000000` ms.
- `gdn`: top `qwen3_next.gdn.replayssm.stage_conv_native` max `49.206947` ms, rank skew `0.000000` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.600796` ms, rank skew `0.000000` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `1408.741751` ms, mean `1408.741751` ms, rank skew `0.000000` ms.
- `gpu_model_runner.model_forward` (runtime): max `1408.590686` ms, mean `1408.590686` ms, rank skew `0.000000` ms.
- `gpu_model_runner.draft_total` (runtime): max `79.249109` ms, mean `79.249109` ms, rank skew `0.000000` ms.
- `qwen3_next.gdn.replayssm.stage_conv_native` (gdn): max `49.206947` ms, mean `49.206947` ms, rank skew `0.000000` ms.
- `qwen3_next.gdn.replayssm.recurrent_native` (gdn): max `8.343733` ms, mean `8.343733` ms, rank skew `0.000000` ms.
- `qwen3_next.gdn.replayssm.commit_pending` (gdn): max `6.544096` ms, mean `6.544096` ms, rank skew `0.000000` ms.
- `qwen3_next.gdn.replayssm.ensure_state` (gdn): max `4.631518` ms, mean `4.631518` ms, rank skew `0.000000` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `1.123968` ms, mean `1.123968` ms, rank skew `0.000000` ms.
- `qwen3_next.gdn.replayssm.pending_mark` (gdn): max `0.922777` ms, mean `0.922777` ms, rank skew `0.000000` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.729380` ms, mean `0.729380` ms, rank skew `0.000000` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.600796` ms, mean `0.600796` ms, rank skew `0.000000` ms.
- `qwen3_next.gdn.replayssm.stage_alloc` (gdn): max `0.417787` ms, mean `0.417787` ms, rank skew `0.000000` ms.
- `gpu_model_runner.sampler` (logits_sampler): max `0.087691` ms, mean `0.087691` ms, rank skew `0.000000` ms.
