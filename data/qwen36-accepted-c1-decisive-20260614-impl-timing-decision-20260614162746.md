# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.quant_method_total at 38.338617 ms). Runner-up is collectives at 6.505370 ms.

## Endpoint Metrics

- Corrected output tok/s: `13.379995702267962`.
- vLLM decode ms/token: `74.73406495410018`.
- TTFT ms: `None`.

## Family Ranking

- `other`: top `moe_forward_shared.custom_op` max `43.376803` ms, rank skew `0.177485` ms.
- `moe`: top `moe.quant_method_total` max `38.338617` ms, rank skew `0.253166` ms.
- `collectives`: top `all_reduce:(1, 2048):torch.bfloat16:bytes=4096` max `6.505370` ms, rank skew `0.097295` ms.
- `runtime`: top `gpu_model_runner.bookkeeping_sync` max `1.288835` ms, rank skew `0.645023` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.271622` ms, rank skew `0.018747` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `73.398709` ms, mean `73.155970` ms, rank skew `0.451976` ms.
- `gpu_model_runner.model_forward` (runtime): max `73.287919` ms, mean `73.055846` ms, rank skew `0.439814` ms.
- `moe_forward_shared.custom_op` (other): max `43.376803` ms, mean `43.278730` ms, rank skew `0.177485` ms.
- `moe.quant_method_total` (moe): max `38.338617` ms, mean `38.198419` ms, rank skew `0.253166` ms.
- `moe.apply` (moe): max `15.404552` ms, mean `15.290620` ms, rank skew `0.265501` ms.
- `all_reduce:(1, 2048):torch.bfloat16:bytes=4096` (collectives): max `6.505370` ms, mean `6.451619` ms, rank skew `0.097295` ms.
- `moe.internal_gate` (moe): max `3.633124` ms, mean `3.555269` ms, rank skew `0.117248` ms.
- `moe.router_select` (moe): max `1.639773` ms, mean `1.617751` ms, rank skew `0.039597` ms.
- `xpu_moe.remap_hidden_states` (moe): max `1.371026` ms, mean `1.351652` ms, rank skew `0.055052` ms.
- `xpu_moe.gemm1_w8a8` (moe): max `1.309842` ms, mean `1.285567` ms, rank skew `0.039258` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `1.288835` ms, mean `1.008012` ms, rank skew `0.645023` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `1.230968` ms, mean `1.152526` ms, rank skew `0.110875` ms.
- `xpu_moe.gemm2_w8a8` (moe): max `1.185852` ms, mean `1.158999` ms, rank skew `0.046526` ms.
- `xpu_moe.gemm1_quant` (moe): max `1.109656` ms, mean `1.075015` ms, rank skew `0.085432` ms.
- `xpu_moe.gemm2_quant` (moe): max `0.926851` ms, mean `0.900229` ms, rank skew `0.047709` ms.
- `xpu_moe.activation` (moe): max `0.685244` ms, mean `0.666305` ms, rank skew `0.045522` ms.
- `xpu_moe.gather` (moe): max `0.600659` ms, mean `0.585223` ms, rank skew `0.042110` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.380799` ms, mean `0.364223` ms, rank skew `0.024267` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.271622` ms, mean `0.258082` ms, rank skew `0.018747` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.155247` ms, mean `0.150108` ms, rank skew `0.007764` ms.
