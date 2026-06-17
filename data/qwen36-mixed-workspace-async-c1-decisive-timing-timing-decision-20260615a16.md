# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe.quant_method_total at 4.648319 ms). Runner-up is gdn at 1.697210 ms.

## Endpoint Metrics

- Corrected output tok/s: `95.53595504341604`.
- vLLM decode ms/token: `10.467712118042982`.
- TTFT ms: `None`.

## Family Ranking

- `other`: top `moe_forward_shared.custom_op` max `5.261113` ms, rank skew `0.729879` ms.
- `moe`: top `moe.quant_method_total` max `4.648319` ms, rank skew `0.688771` ms.
- `gdn`: top `gdn_attention_core_xpu.native` max `1.697210` ms, rank skew `0.095146` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.229083` ms, rank skew `0.008960` ms.
- `runtime`: top `gpu_model_runner.async_output_wrap` max `0.113850` ms, rank skew `0.007485` ms.
- `collectives`: top `all_reduce:(48, 2048):torch.bfloat16:bytes=196608` max `0.054620` ms, rank skew `0.001666` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `5.900765` ms, mean `5.707079` ms, rank skew `0.274050` ms.
- `gpu_model_runner.model_forward` (runtime): max `5.845483` ms, mean `5.652852` ms, rank skew `0.272731` ms.
- `moe_forward_shared.custom_op` (other): max `5.261113` ms, mean `4.841766` ms, rank skew `0.729879` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `4.674168` ms, mean `4.573021` ms, rank skew `0.338040` ms.
- `moe.quant_method_total` (moe): max `4.648319` ms, mean `4.251403` ms, rank skew `0.688771` ms.
- `gdn_attention_core_xpu.native` (gdn): max `1.697210` ms, mean `1.633897` ms, rank skew `0.095146` ms.
- `moe.apply` (moe): max `1.555304` ms, mean `1.516779` ms, rank skew `0.071521` ms.
- `moe.internal_gate` (moe): max `0.426615` ms, mean `0.414009` ms, rank skew `0.024188` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.309844` ms, mean `0.301023` ms, rank skew `0.013196` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.229083` ms, mean `0.223176` ms, rank skew `0.008960` ms.
- `moe.router_select` (moe): max `0.185414` ms, mean `0.179237` ms, rank skew `0.010671` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.156844` ms, mean `0.136555` ms, rank skew `0.028229` ms.
- `xpu_moe.gemm1_w8a8` (moe): max `0.138978` ms, mean `0.136470` ms, rank skew `0.007653` ms.
- `gpu_model_runner.sampler` (logits_sampler): max `0.135142` ms, mean `0.117475` ms, rank skew `0.024563` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.133954` ms, mean `0.131027` ms, rank skew `0.005338` ms.
- `gpu_model_runner.async_output_wrap` (runtime): max `0.113850` ms, mean `0.108945` ms, rank skew `0.007485` ms.
- `xpu_moe.gemm2_w8a8` (moe): max `0.112670` ms, mean `0.109993` ms, rank skew `0.005089` ms.
- `logits.local_argmax_lm_head` (logits_sampler): max `0.071349` ms, mean `0.070146` ms, rank skew `0.002412` ms.
- `xpu_moe.gemm1_quant` (moe): max `0.064374` ms, mean `0.062763` ms, rank skew `0.002817` ms.
- `xpu_moe.activation` (moe): max `0.059565` ms, mean `0.057079` ms, rank skew `0.003926` ms.
