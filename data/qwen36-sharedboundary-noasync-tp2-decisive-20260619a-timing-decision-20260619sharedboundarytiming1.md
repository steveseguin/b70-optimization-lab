# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `persistent_w8a8_moe_layerlet`.
- Leading family: `moe`.
- Decision basis: `aggregate_exit_summary`.
- Reason: moe has the largest visible per-family label (moe_forward_shared.custom_op at 4.854578 ms). Runner-up is runtime at 4.707160 ms.

## Endpoint Metrics

- Corrected output tok/s: `84.10955623702061`.
- vLLM decode ms/token: `11.891772437593318`.
- TTFT ms: `None`.

## Family Ranking

- `moe`: top `moe_forward_shared.custom_op` max `4.854578` ms, rank skew `0.024842` ms.
- `runtime`: top `gpu_model_runner.bookkeeping_sync` max `4.707160` ms, rank skew `0.002113` ms.
- `gdn`: top `gdn_attention_core_xpu.native` max `1.565822` ms, rank skew `0.011544` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.215202` ms, rank skew `0.000577` ms.
- `collectives`: top `all_reduce:(48, 2048):torch.bfloat16:bytes=196608` max `0.053931` ms, rank skew `0.002695` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `6.176259` ms, mean `6.172866` ms, rank skew `0.006786` ms.
- `gpu_model_runner.model_forward` (runtime): max `6.126101` ms, mean `6.122397` ms, rank skew `0.007409` ms.
- `moe_forward_shared.custom_op` (moe): max `4.854578` ms, mean `4.842157` ms, rank skew `0.024842` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `4.707160` ms, mean `4.706104` ms, rank skew `0.002113` ms.
- `moe.quant_method_total` (moe): max `4.278461` ms, mean `4.261922` ms, rank skew `0.033077` ms.
- `moe.shared_experts.apply_no_overlap` (moe): max `2.231378` ms, mean `2.185991` ms, rank skew `0.090773` ms.
- `moe.apply` (moe): max `1.748564` ms, mean `1.685254` ms, rank skew `0.126620` ms.
- `qwen2_moe.shared.boundary_int8_cpp` (moe): max `1.579748` ms, mean `1.548210` ms, rank skew `0.063075` ms.
- `gdn_attention_core_xpu.native` (gdn): max `1.565822` ms, mean `1.560050` ms, rank skew `0.011544` ms.
- `xpu_moe.fused_moe_call` (moe): max `1.181251` ms, mean `1.114463` ms, rank skew `0.133576` ms.
- `gpu_model_runner.preprocess_total` (runtime): max `1.070254` ms, mean `1.069216` ms, rank skew `0.002076` ms.
- `moe.internal_gate` (moe): max `0.387493` ms, mean `0.385906` ms, rank skew `0.003173` ms.
- `xpu_moe.remap_hidden_states` (moe): max `0.358647` ms, mean `0.239017` ms, rank skew `0.239259` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `0.292649` ms, mean `0.292385` ms, rank skew `0.000529` ms.
- `xpu_moe.gemm2_w8a8` (moe): max `0.223618` ms, mean `0.175532` ms, rank skew `0.096172` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.215202` ms, mean `0.214914` ms, rank skew `0.000577` ms.
- `xpu_moe.workspace_scratch_get` (moe): max `0.188419` ms, mean `0.181836` ms, rank skew `0.013166` ms.
- `moe.router_select` (moe): max `0.173576` ms, mean `0.172519` ms, rank skew `0.002115` ms.
- `xpu_moe.gemm1_w8a8` (moe): max `0.130199` ms, mean `0.128694` ms, rank skew `0.003010` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `0.127755` ms, mean `0.124460` ms, rank skew `0.006590` ms.
