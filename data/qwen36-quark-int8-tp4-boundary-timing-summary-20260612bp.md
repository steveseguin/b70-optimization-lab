# Qwen3.6 Boundary Timing Summary 20260612bp

Scope: diagnostic timing run only. Same current Quark W8A8 INT8 TP4 model/service posture, with env-gated rank-0 timing labels enabled.

## Endpoint Metrics

- `tok_s_out_client_after_first_chunk_corrected` median: `99.79580058372702`
- `tok_s_out_client_e2e` median: `96.97711495070851`
- `decode_ms_per_generation_token_vllm_histogram` median: `9.983932288832875`
- `time_per_output_token_ms_vllm_histogram` median: `10.023084964475355`
- `ttft_ms_client` median: `84.58438294474036`
- `queue_ms_vllm_histogram` median: `0.007538823410868645`
- `prefill_ms_vllm_histogram` median: `77.58979662321508`

## Rank-0 Pure Decode Step Timing

- Step lines parsed: `34`
- Summary lines parsed: `36`
- Bucket: decode_bucket `1`, padded tokens `1`, steps `34`
- Mean overlapping timed labels per sampled step: `13.769678970588235` ms
- Mean `gpu_model_runner.model_forward`: `5.593065382352941` ms

| label | mean ms/step | median ms/step | p90 ms/step | calls |
|---|---:|---:|---:|---:|
| `gpu_model_runner.forward_total` | 5.648344 | 5.607458 | 5.666464 | 34 |
| `gpu_model_runner.model_forward` | 5.593065 | 5.550717 | 5.609337 | 34 |
| `gdn_attention_core_xpu.native` | 1.507163 | 1.493222 | 1.529630 | 1020 |
| `gpu_model_runner.postprocess_total` | 0.308149 | 0.302959 | 0.329574 | 34 |
| `gpu_model_runner.compute_logits` | 0.228452 | 0.224757 | 0.241328 | 34 |
| `gpu_model_runner.sample_total` | 0.162182 | 0.160862 | 0.169258 | 34 |
| `gpu_model_runner.sampler` | 0.138420 | 0.135765 | 0.146615 | 34 |
| `gpu_model_runner.async_output_wrap` | 0.103500 | 0.102893 | 0.107253 | 34 |
| `gpu_model_runner.select_sample_hidden` | 0.050890 | 0.048862 | 0.056321 | 34 |
| `gpu_model_runner.bookkeeping_sync` | 0.029514 | 0.028909 | 0.030091 | 34 |

## Interpretation

- Endpoint decode is `9.983932 ms/token`; sampled rank-0 no-sync model-forward is `5.593065 ms/token`, leaving about `4.390867 ms/token` unexplained by this asynchronous rank-0 forward proxy.
- `gpu_model_runner.forward_total` and `model_forward` are nearly identical, so the newly added boundary label does not reveal large Python overhead inside forward wrapping.
- Postprocess, logits, sampler, and async output wrap are sub-millisecond together in the sampled rank-0 pure-decode steps.
- Timing labels here are nested and overlapping, not exclusive slices. They should not be summed into a token budget.
- The next timing work should account for scheduler/engine step wall time, rank-to-rank variance, collectives across all ranks, and any host/device synchronization not visible in rank-0 forward labels.
