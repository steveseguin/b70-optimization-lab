# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.quant_method_total at 4.535820 ms). Runner-up is runtime at 3.923906 ms.

## Endpoint Metrics

- Corrected output tok/s: `92.52199961749443`.
- vLLM decode ms/token: `10.809507781232242`.
- TTFT ms: `None`.

## Family Ranking

- `other`: top `moe_forward_shared.custom_op` max `5.157303` ms, rank skew `0.216721` ms.
- `moe`: top `moe.quant_method_total` max `4.535820` ms, rank skew `0.207469` ms.
- `runtime`: top `gpu_model_runner.bookkeeping_sync` max `3.923906` ms, rank skew `0.147049` ms.
- `gdn`: top `gdn_attention_core_xpu.native` max `1.639102` ms, rank skew `0.062791` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.251656` ms, rank skew `0.012373` ms.
- `collectives`: top `all_reduce:(48, 2048):torch.bfloat16:bytes=196608` max `0.055205` ms, rank skew `0.003307` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `5.782898` ms, mean `5.692320` ms, rank skew `0.130189` ms.
- `gpu_model_runner.model_forward` (runtime): max `5.721680` ms, mean `5.631813` ms, rank skew `0.129452` ms.
- `moe_forward_shared.custom_op` (other): max `5.157303` ms, mean `5.093521` ms, rank skew `0.216721` ms.
- `moe.quant_method_total` (moe): max `4.535820` ms, mean `4.471597` ms, rank skew `0.207469` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `3.923906` ms, mean `3.883560` ms, rank skew `0.147049` ms.
- `moe.apply` (moe): max `1.710406` ms, mean `1.700161` ms, rank skew `0.018499` ms.
- `gdn_attention_core_xpu.native` (gdn): max `1.639102` ms, mean `1.599332` ms, rank skew `0.062791` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `0.961622` ms, mean `0.945053` ms, rank skew `0.025723` ms.
- `moe.internal_gate` (moe): max `0.441132` ms, mean `0.436529` ms, rank skew `0.010536` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.332912` ms, mean `0.323859` ms, rank skew `0.014422` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.251656` ms, mean `0.244393` ms, rank skew `0.012373` ms.
- `moe.router_select` (moe): max `0.190619` ms, mean `0.189468` ms, rank skew `0.001995` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.142566` ms, mean `0.141084` ms, rank skew `0.002807` ms.
- `xpu_moe.gemm1_w8a8` (moe): max `0.139575` ms, mean `0.137919` ms, rank skew `0.003564` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.127117` ms, mean `0.125341` ms, rank skew `0.003751` ms.
- `gpu_model_runner.sampler` (logits_sampler): max `0.120664` ms, mean `0.118965` ms, rank skew `0.003592` ms.
- `xpu_moe.gemm2_w8a8` (moe): max `0.118790` ms, mean `0.118053` ms, rank skew `0.001425` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.099346` ms, mean `0.098559` ms, rank skew `0.002240` ms.
- `xpu_moe.gemm2_quant` (moe): max `0.083442` ms, mean `0.082825` ms, rank skew `0.001519` ms.
- `logits.local_argmax_lm_head` (logits_sampler): max `0.080289` ms, mean `0.077799` ms, rank skew `0.004038` ms.
