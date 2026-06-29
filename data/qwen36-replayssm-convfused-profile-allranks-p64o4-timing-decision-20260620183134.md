# Qwen3.6 Timing Family Decision

This is a routing artifact, not a speed claim. Timing labels are nested;
family sums are non-exclusive.

## Decision

- Next target: `gdn_dense_w8a8_quant_gemm_fusion`.
- Leading family: `gdn`.
- Decision basis: `aggregate_exit_summary`.
- Reason: gdn has the largest visible per-family label (qwen3_next.gdn.replayssm.ensure_state at 215.688643 ms). Runner-up is runtime at 192.958295 ms.

## Endpoint Metrics

- Corrected output tok/s: `0.6485502506044699`.
- vLLM decode ms/token: `2824.761661249795`.
- TTFT ms: `None`.

## Family Ranking

- `gdn`: top `qwen3_next.gdn.replayssm.ensure_state` max `215.688643` ms, rank skew `207.042275` ms.
- `runtime`: top `gpu_model_runner.draft_total` max `192.958295` ms, rank skew `182.960221` ms.
- `other`: top `spec_decode.greedy_sample_total` max `2.388804` ms, rank skew `1.890356` ms.
- `logits_sampler`: top `gpu_model_runner.compute_logits` max `0.875656` ms, rank skew `0.290135` ms.

## Top Labels

- `gpu_model_runner.forward_total` (runtime): max `2229.599588` ms, mean `2078.082008` ms, rank skew `262.431824` ms.
- `gpu_model_runner.model_forward` (runtime): max `2229.438071` ms, mean `2077.936499` ms, rank skew `262.414085` ms.
- `qwen3_next.gdn.replayssm.ensure_state` (gdn): max `215.688643` ms, mean `61.815364` ms, rank skew `207.042275` ms.
- `gpu_model_runner.draft_total` (runtime): max `192.958295` ms, mean `56.410120` ms, rank skew `182.960221` ms.
- `qwen3_next.gdn.replayssm.stage_conv_native` (gdn): max `139.734157` ms, mean `100.501959` ms, rank skew `132.945128` ms.
- `qwen3_next.gdn.replayssm.recurrent_native` (gdn): max `16.526419` ms, mean `13.915760` ms, rank skew `4.636576` ms.
- `gpu_model_runner.async_output_wrap` (runtime): max `4.292400` ms, mean `3.304886` ms, rank skew `2.732004` ms.
- `gpu_model_runner.sample_total` (logits_sampler): max `3.668369` ms, mean `1.922429` ms, rank skew `2.725116` ms.
- `gpu_model_runner.rejection_sampler` (runtime): max `3.440150` ms, mean `1.777495` ms, rank skew `2.607873` ms.
- `spec_decode.greedy_sample_total` (other): max `2.388804` ms, mean `0.976036` ms, rank skew `1.890356` ms.
- `spec_decode.greedy_sample.compute_logits` (other): max `2.184232` ms, mean `0.848905` ms, rank skew `1.786123` ms.
- `spec_decode.propose.model_forward_first` (other): max `1.820237` ms, mean `0.921554` ms, rank skew `1.210285` ms.
- `qwen3_next.gdn.replayssm.commit_pending` (gdn): max `1.583335` ms, mean `1.262084` ms, rank skew `0.461384` ms.
- `gpu_model_runner.postprocess_total` (runtime): max `1.023875` ms, mean `0.817568` ms, rank skew `0.308703` ms.
- `qwen3_next.gdn.replayssm.stage_alloc` (gdn): max `0.942967` ms, mean `0.470004` ms, rank skew `0.651523` ms.
- `qwen3_next.gdn.replayssm.pending_mark` (gdn): max `0.888956` ms, mean `0.715315` ms, rank skew `0.257124` ms.
- `gpu_model_runner.compute_logits` (logits_sampler): max `0.875656` ms, mean `0.690850` ms, rank skew `0.290135` ms.
- `spec_decode.propose.set_inputs_first_pass` (other): max `0.522637` ms, mean `0.266073` ms, rank skew `0.349384` ms.
- `gpu_model_runner.bookkeeping_sync` (runtime): max `0.476318` ms, mean `0.183231` ms, rank skew `0.403429` ms.
- `spec_decode.propose.determine_padding_first` (other): max `0.328372` ms, mean `0.106853` ms, rank skew `0.297161` ms.
