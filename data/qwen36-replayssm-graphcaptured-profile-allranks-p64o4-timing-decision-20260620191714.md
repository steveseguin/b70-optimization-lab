# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `scheduler_runtime_static_c1_lane`.
- Leading family: `runtime`.
- Decision basis: `aggregate_exit_summary`.
- Reason: runtime has the largest visible per-family label (gpu_model_runner.draft_total at 1371.591390 ms). Runner-up is logits_sampler at 0.749346 ms.

## Endpoint Metrics

- Corrected output tok/s: `0.23771019080785555`.
- vLLM decode ms/token: `6423.130989749552`.
- TTFT ms: `None`.

## Family Ranking

- `runtime`: top `gpu_model_runner.draft_total` max `1371.591390` ms, rank skew `114.649982` ms.
- `other`: top `spec_decode.greedy_sample_total` max `2.708801` ms, rank skew `2.029189` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.749346` ms, rank skew `0.245182` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `2995.793261` ms, mean `2984.211224` ms, rank skew `27.244097` ms.
- `gpu_model_runner.model_forward` (runtime): max `2995.653917` ms, mean `2984.041521` ms, rank skew `27.258581` ms.
- `gpu_model_runner.draft_total` (runtime): max `1371.591390` ms, mean `1289.504030` ms, rank skew `114.649982` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `581.414785` ms, mean `540.837437` ms, rank skew `87.372836` ms.
- `gpu_model_runner.rejection_sampler` (runtime): max `581.305684` ms, mean `540.715763` ms, rank skew `87.369587` ms.
- `spec_decode.greedy_sample_total` (other): max `2.708801` ms, mean `1.256679` ms, rank skew `2.029189` ms.
- `spec_decode.greedy_sample.compute_logits` (other): max `2.193221` ms, mean `0.969170` ms, rank skew `1.733679` ms.
- `spec_decode.propose.model_forward_first` (other): max `2.137901` ms, mean `1.171459` ms, rank skew `1.382384` ms.
- `gpu_model_runner.async_output_wrap` (runtime): max `1.571087` ms, mean `0.835409` ms, rank skew `1.159397` ms.
- `spec_decode.propose.set_inputs_first_pass` (other): max `0.938538` ms, mean `0.465482` ms, rank skew `0.681973` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.895645` ms, mean `0.786192` ms, rank skew `0.260768` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.749346` ms, mean `0.585821` ms, rank skew `0.245182` ms.
- `spec_decode.greedy_sample.argmax` (other): max `0.493135` ms, mean `0.264760` ms, rank skew `0.322698` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `0.447272` ms, mean `0.236809` ms, rank skew `0.337544` ms.
- `spec_decode.propose.select_sample_hidden_first` (other): max `0.121642` ms, mean `0.093705` ms, rank skew `0.047753` ms.
- `gpu_model_runner.sampler` (logits_sampler): max `0.097396` ms, mean `0.068155` ms, rank skew `0.040336` ms.
- `gpu_model_runner.select_sample_hidden` (logits_sampler): max `0.063149` ms, mean `0.056192` ms, rank skew `0.010719` ms.
- `spec_decode.propose.determine_padding_first` (other): max `0.044345` ms, mean `0.037840` ms, rank skew `0.011817` ms.
- `spec_decode.propose.build_attn_metadata_first` (other): max `0.037402` ms, mean `0.030208` ms, rank skew `0.011640` ms.
- `spec_decode.propose.build_model_inputs_first` (other): max `0.016063` ms, mean `0.013845` ms, rank skew `0.003688` ms.
