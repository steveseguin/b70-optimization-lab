# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.quant_method_total at 8.420433 ms). Runner-up is gdn at 1.690804 ms.

## Endpoint Metrics

- Corrected output tok/s: `84.64666751559521`.
- vLLM decode ms/token: `11.876532875248813`.
- TTFT ms: `None`.

## Family Ranking

- `other`: top `moe_forward_shared.custom_op` max `9.059154` ms, rank skew `0.464021` ms.
- `moe`: top `moe.quant_method_total` max `8.420433` ms, rank skew `0.463098` ms.
- `gdn`: top `gdn_attention_core_xpu.native` max `1.690804` ms, rank skew `0.101601` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.236584` ms, rank skew `0.003680` ms.
- `runtime`: top `gpu_model_runner.async_output_wrap` max `0.111625` ms, rank skew `0.004864` ms.
- `collectives`: top `all_reduce:(24, 2048):torch.bfloat16:bytes=98304` max `0.062689` ms, rank skew `0.029117` ms.

## Top Labels

- `moe_forward_shared.custom_op` (other): max `9.059154` ms, mean `8.866614` ms, rank skew `0.464021` ms.
- `moe.quant_method_total` (moe): max `8.420433` ms, mean `8.225290` ms, rank skew `0.463098` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `6.412582` ms, mean `6.201525` ms, rank skew `0.453091` ms.
- `gpu_model_runner.forward_total` (runtime): max `6.057856` ms, mean `5.882305` ms, rank skew `0.249350` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.002461` ms, mean `5.825167` ms, rank skew `0.252255` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `5.723376` ms, mean `5.643232` ms, rank skew `0.258913` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `3.996773` ms, mean `3.928330` ms, rank skew `0.224044` ms.
- `gdn_attention_core_xpu.native` (gdn): max `1.690804` ms, mean `1.624738` ms, rank skew `0.101601` ms.
- `moe.apply` (moe): max `1.639301` ms, mean `1.603309` ms, rank skew `0.056383` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.039104` ms, mean `1.009785` ms, rank skew `0.048651` ms.
- `qwen2_moe.shared.down_proj` (moe): max `0.723944` ms, mean `0.704992` ms, rank skew `0.054652` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `0.665341` ms, mean `0.529847` ms, rank skew `0.288087` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.451749` ms, mean `0.448041` ms, rank skew `0.008510` ms.
- `moe.internal_gate` (moe): max `0.428050` ms, mean `0.426146` ms, rank skew `0.005878` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.381766` ms, mean `0.379500` ms, rank skew `0.005538` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.318902` ms, mean `0.315453` ms, rank skew `0.006781` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.236584` ms, mean `0.234827` ms, rank skew `0.003680` ms.
- `moe.router_select` (moe): max `0.192314` ms, mean `0.191144` ms, rank skew `0.002651` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.178456` ms, mean `0.175771` ms, rank skew `0.006616` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.160995` ms, mean `0.145007` ms, rank skew `0.024293` ms.
