# 2026-05-31 vLLM Code Survey

Local checkout: `/home/steve/src/vllm`

## Relevant Existing Support

- Model registry maps `DeepseekV4ForCausalLM` to `vllm/model_executor/models/deepseek_v4.py`.
- Config path rewrites DeepSeek V4 fp8 quantization to `deepseek_v4_fp8`, but
  AutoRound should route through `inc` because the HF quant method is
  `auto-round`.
- Local `vllm/model_executor/layers/quantization/inc.py` already contains the
  MiniMax-era XPU path that returns `MoeWNA16Config` for `FusedMoE`. This is a
  useful starting point for DeepSeek V4 W4A16 experts.

## Likely First Failures

These are code-inspection findings, not benchmark results.

1. `DeepseekV4Model.__init__` creates:

   ```python
   aux_stream_list = [torch.cuda.Stream() for _ in range(3)]
   ```

   That is CUDA-specific and should be guarded before XPU model construction.

2. `DeepseekV4MLAAttention.__init__` creates:

   ```python
   self.ln_events = [torch.cuda.Event(), torch.cuda.Event()]
   ```

   This is also CUDA-specific.

3. `DeepseekV4MLAAttention` asserts the attention backend is
   `FlashMLASparseBackend` and forces/uses `fp8_ds_mla` KV. That backend is
   probably the real XPU bring-up blocker after stream/event guards.

4. `DeepseekV4MegaMoEExperts._check_runtime_supported()` rejects non-CUDA and
   non-SM100. Do not enable `deep_gemm_mega_moe` on B70. Use the regular
   `FusedMoE` path first.

5. DeepSeek V4 uses hyper-connections through `mhc_pre`, `mhc_post`, and
   `hc_head_fused_kernel`. These custom ops need separate XPU verification.

## Patch Order

1. Make model construction platform-safe without changing execution semantics on
   CUDA.
2. Run dummy or tiny load to expose the next failure.
3. Add the smallest correctness fallback for sparse MLA/KV on XPU.
4. Verify INC W4A16 dense and `FusedMoE` paths load the checkpoint names.
5. Only then start B70 tile/config optimization.

## Do Not Do Yet

- Do not port MegaMoE first. It is CUDA/SM100-specialized and not the path to a
  first B70 smoke.
- Do not submit LocalMaxxing numbers from fallback/dequantized paths unless the
  payload explicitly says they are diagnostic baselines.
- Do not chase long context before p64/n16 and p512/n128 are quality-clean.
