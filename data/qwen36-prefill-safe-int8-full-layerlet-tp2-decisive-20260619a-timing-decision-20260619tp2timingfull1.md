# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe_forward_shared.custom_op at 8.720514 ms). Runner-up is gdn at 1.699722 ms.

## Endpoint Metrics

- Corrected output tok/s: `84.4112340056149`.
- vLLM decode ms/token: `11.845327250739501`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe_forward_shared.custom_op` max `8.720514` ms, rank skew `0.167053` ms.
- `gdn`: top `gdn_attention_core_xpu.native` max `1.699722` ms, rank skew `0.022940` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.235926` ms, rank skew `0.001969` ms.
- `runtime`: top `gpu_model_runner.async_output_wrap` max `0.109592` ms, rank skew `0.000486` ms.
- `collectives`: top `all_reduce:(48, 2048):torch.bfloat16:bytes=196608` max `0.058571` ms, rank skew `0.000431` ms.

## Top Labels

- `moe_forward_shared.custom_op` (moe): max `8.720514` ms, mean `8.636988` ms, rank skew `0.167053` ms.
- `moe.quant_method_total` (moe): max `8.047654` ms, mean `7.965041` ms, rank skew `0.165225` ms.
- `gpu_model_runner.forward_total` (runtime): max `6.544621` ms, mean `6.481376` ms, rank skew `0.126490` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.488467` ms, mean `6.425878` ms, rank skew `0.125179` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `5.635415` ms, mean `5.572366` ms, rank skew `0.126099` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `5.589111` ms, mean `5.503924` ms, rank skew `0.170372` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `3.311749` ms, mean `3.304482` ms, rank skew `0.014534` ms.
- `moe.apply` (moe): max `1.978799` ms, mean `1.960837` ms, rank skew `0.035924` ms.
- `gdn_attention_core_xpu.native` (gdn): max `1.699722` ms, mean `1.688252` ms, rank skew `0.022940` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.342872` ms, mean `1.322405` ms, rank skew `0.040935` ms.
- `qwen2_moe.shared.down_proj` (moe): max `0.687022` ms, mean `0.673057` ms, rank skew `0.027930` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.598805` ms, mean `0.527290` ms, rank skew `0.143030` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `0.455416` ms, mean `0.433064` ms, rank skew `0.044703` ms.
- `moe.internal_gate` (moe): max `0.449670` ms, mean `0.448890` ms, rank skew `0.001561` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.405681` ms, mean `0.403268` ms, rank skew `0.004826` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.391608` ms, mean `0.263468` ms, rank skew `0.256282` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.317192` ms, mean `0.315048` ms, rank skew `0.004289` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.235926` ms, mean `0.234941` ms, rank skew `0.001969` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.203953` ms, mean `0.202640` ms, rank skew `0.002627` ms.
- `moe.router_select` (moe): max `0.190999` ms, mean `0.190539` ms, rank skew `0.000921` ms.
