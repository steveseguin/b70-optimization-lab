# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe_forward_shared.custom_op at 8.841024 ms). Runner-up is gdn at 1.747878 ms.

## Endpoint Metrics

- Corrected output tok/s: `84.30754286685192`.
- vLLM decode ms/token: `11.861692133606994`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe_forward_shared.custom_op` max `8.841024` ms, rank skew `0.322746` ms.
- `gdn`: top `gdn_attention_core_xpu.native` max `1.747878` ms, rank skew `0.113830` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.227998` ms, rank skew `0.015266` ms.
- `runtime`: top `gpu_model_runner.async_output_wrap` max `0.110831` ms, rank skew `0.008128` ms.
- `collectives`: top `all_reduce:(48, 2048):torch.bfloat16:bytes=196608` max `0.059611` ms, rank skew `0.002320` ms.

## Top Labels

- `moe_forward_shared.custom_op` (moe): max `8.841024` ms, mean `8.679651` ms, rank skew `0.322746` ms.
- `moe.quant_method_total` (moe): max `8.172749` ms, mean `8.004540` ms, rank skew `0.336419` ms.
- `gpu_model_runner.forward_total` (runtime): max `6.654150` ms, mean `6.446875` ms, rank skew `0.414551` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.601765` ms, mean `6.395494` ms, rank skew `0.412542` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `5.837228` ms, mean `5.584714` ms, rank skew `0.505028` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `5.772847` ms, mean `5.731271` ms, rank skew `0.083151` ms.
- `qwen2_moe.shared.silu_and_mul` (moe): max `3.394437` ms, mean `3.382293` ms, rank skew `0.024288` ms.
- `moe.apply` (moe): max `1.964126` ms, mean `1.836025` ms, rank skew `0.256202` ms.
- `gdn_attention_core_xpu.native` (gdn): max `1.747878` ms, mean `1.690963` ms, rank skew `0.113830` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.318158` ms, mean `1.190214` ms, rank skew `0.255887` ms.
- `qwen2_moe.shared.down_proj` (moe): max `0.674385` ms, mean `0.655563` ms, rank skew `0.037645` ms.
- `qwen2_moe.shared.gate_up_proj` (moe): max `0.655712` ms, mean `0.636020` ms, rank skew `0.039385` ms.
- `moe.internal_gate` (moe): max `0.451233` ms, mean `0.449876` ms, rank skew `0.002714` ms.
- `qwen2_moe.shared.gate_mul` (moe): max `0.436992` ms, mean `0.422093` ms, rank skew `0.029799` ms.
- `qwen2_moe.shared.expert_gate` (moe): max `0.405421` ms, mean `0.405137` ms, rank skew `0.000568` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.397847` ms, mean `0.267956` ms, rank skew `0.259782` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.310346` ms, mean `0.300060` ms, rank skew `0.020571` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.227998` ms, mean `0.220365` ms, rank skew `0.015266` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.202013` ms, mean `0.201772` ms, rank skew `0.000481` ms.
- `moe.router_select` (moe): max `0.194651` ms, mean `0.193403` ms, rank skew `0.002497` ms.
