# Ideas Backlog

Move an item into `results/experiment-ledger.md` once it has been tested.

## Loader And Correctness

- XPU-guard `torch.cuda.Stream()` and `torch.cuda.Event()` in DeepSeek V4 model
  construction.
- Probe whether `--kv-cache-dtype fp8` becomes `fp8_ds_mla` on XPU or fails
  before attention construction.
- Add a dummy-load construction test that does not require the full 153 GB
  safetensors download.
- Confirm AutoRound `extra_config` keeps `lm_head` and embeddings unquantized.
- Confirm hash-MoE routing table dtype and weight mapping on TP4.

## Attention

- Determine whether the current FlashMLA sparse backend has any XPU path.
- If no XPU path exists, build a correctness-first fallback using the official
  inference sparse attention logic as a reference.
- Separate sliding-window cache and compressed-cache correctness tests.
- Benchmark p64/n16 before optimizing kernels.

## MoE

- Keep `FusedMoE` path first; avoid CUDA/SM100 `deep_gemm_mega_moe`.
- Reuse MiniMax INC/XPU W4A16 MoE dispatch lessons.
- After correctness, tune `E=256`, local experts `64`, `N=2048`,
  top-k `6`, hidden `4096`, dtype `int4_w4a16` for B70.
- Check whether shared expert and routed experts take different quant methods.

## Runtime And Scheduling

- Compare `CCL_ZE_IPC_EXCHANGE=pidfd` vs default after first successful run.
- Test `--enforce-eager` only as a failure isolation tool.
- Test compile modes only after baseline quality.
- Keep `max_model_len=2048` until capacity behavior is known.
