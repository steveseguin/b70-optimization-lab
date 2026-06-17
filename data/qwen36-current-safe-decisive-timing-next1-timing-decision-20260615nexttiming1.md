# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe_forward_shared.custom_op at 5.553667 ms). Runner-up is gdn at 1.668219 ms.

## Endpoint Metrics

- Corrected output tok/s: `95.078788891372`.
- vLLM decode ms/token: `10.518892210711783`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe_forward_shared.custom_op` max `5.553667` ms, rank skew `0.142176` ms.
- `gdn`: top `gdn_attention_core_xpu.native` max `1.668219` ms, rank skew `0.080413` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.233964` ms, rank skew `0.012712` ms.
- `runtime`: top `gpu_model_runner.async_output_wrap` max `0.112965` ms, rank skew `0.006201` ms.
- `collectives`: top `all_reduce:(16, 2048):torch.bfloat16:bytes=65536` max `0.071001` ms, rank skew `0.039260` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `5.930162` ms, mean `5.749105` ms, rank skew `0.277056` ms.
- `gpu_model_runner.model_forward` (runtime): max `5.873232` ms, mean `5.694941` ms, rank skew `0.274299` ms.
- `moe_forward_shared.custom_op` (moe): max `5.553667` ms, mean `5.482126` ms, rank skew `0.142176` ms.
- `moe.quant_method_total` (moe): max `4.916672` ms, mean `4.848441` ms, rank skew `0.140868` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `4.687118` ms, mean `4.573534` ms, rank skew `0.347613` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `2.900636` ms, mean `2.801782` ms, rank skew `0.188112` ms.
- `gdn_attention_core_xpu.native` (gdn): max `1.668219` ms, mean `1.615982` ms, rank skew `0.080413` ms.
- `moe.apply` (moe): max `1.655344` ms, mean `1.637574` ms, rank skew `0.049479` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.060127` ms, mean `1.044751` ms, rank skew `0.040723` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `0.793811` ms, mean `0.780490` ms, rank skew `0.024766` ms.
- `qwen2_moe.shared.down_proj` (moe): max `0.681494` ms, mean `0.674716` ms, rank skew `0.014170` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.465057` ms, mean `0.451944` ms, rank skew `0.020552` ms.
- `moe.internal_gate` (moe): max `0.434964` ms, mean `0.427187` ms, rank skew `0.015308` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `0.393501` ms, mean `0.307832` ms, rank skew `0.162423` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.383105` ms, mean `0.379954` ms, rank skew `0.008390` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.313827` ms, mean `0.303393` ms, rank skew `0.015922` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.233964` ms, mean `0.225741` ms, rank skew `0.012712` ms.
- `moe.router_select` (moe): max `0.185784` ms, mean `0.184564` ms, rank skew `0.002679` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.183457` ms, mean `0.181706` ms, rank skew `0.002538` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.161214` ms, mean `0.139441` ms, rank skew `0.029966` ms.
