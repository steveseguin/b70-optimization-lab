# R276 target-only FP8 compatibility audit

Conclusion: the installed Python dispatch supports the pinned official Qwen3.8 27B block-FP8 architecture. No Python-side persistent FP16/BF16 copy of all block-FP8 weights is created along the selected XPU block-W8A16 path. This is source compatibility evidence, not model loading, memory-capacity, correctness or serving qualification. No GPU device, model construction, network endpoint or server was used.

## Exact installed source

Both inspection receipts record the immutable image `sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad` and successful CPU-only processes: network disabled, no device mounts, read-only root, all capabilities dropped, one CPU, 1 GiB memory and equal combined memory/swap. Both owned containers exited normally and were auto-removed. Earlier `docker cp` from the stopped GPU container could not resolve paths after its model bind source was removed; it supplied no source bytes.

Installed package metadata identifies vLLM `0.27.2rc1.dev77+gac7509e2b.xpu` and vLLM-XPU-kernels `0.1.dev1+g1e90ffa67`. Upstream SPDX notices remain in each copied source, and both installed Apache-2.0 license files are retained under their dist-info directories.

- `installed/vllm/model_executor/models/registry.py:592` registers `Qwen3_5ForConditionalGeneration`; `installed/vllm/platforms/xpu.py:119` includes `fp8`.
- `installed/vllm/model_executor/layers/quantization/fp8.py:324` creates the FP8 weight parameter; `installed/vllm/model_executor/layers/quantization/utils/fp8_utils.py:1244` allocates it as `torch.float8_e4m3fn`. The block strategy at line 1368 returns FP8 weights plus scales, with optional FP8 layout padding.
- `installed/vllm/model_executor/kernels/linear/__init__.py:451` selects the XPU block kernel before its fallbacks.
- `installed/vllm/model_executor/kernels/linear/scaled_mm/xpu.py:193` contains `XPUFp8BlockScaledMMKernel`; SHA-256 `7c36e4a8dab4bfc06b1d5be2d8466e8cdc94099dd5409424fecc6dd8ffc2c208`. Its enabled `VLLM_XPU_FP8_BLOCK_W8A16=1` gate disables activation FP8 quantization and requires `_xpu_C.fp8_gemm_w8a16`. Weight processing keeps weights unchanged and transposes/expands scales; `apply_block_scaled_mm` sends `B.t()` as a view directly to that operator. No half-weight cache is allocated in this Python path.
- `installed/vllm/model_executor/kernels/linear/scaled_mm/BlockScaledMMLinearKernel.py` similarly retains the FP8 parameter and forwards it, without an FP16/BF16 parameter cache.

The installed distribution does not contain the requested C++ header. `kernel-base-source/` separately retains that header and license from the image-labelled base commit `1e90ffa672ba02f17a909da11838a4c55b199783`, recovered read-only from local Git. This is not a claim that the base header alone reproduces the patched image binary. That header uses f16_f8 oneDNN dtype, forwards `mat2.data_ptr()` and creates per-call byte scratchpad; primitive-cache or allocator internals still require actual runtime memory observation. No guarantee of fitting 32 GiB per card is inferred. Budget ordinary unquantized layers, KV/GDN state, temporaries and allocator overhead separately.

## Restricted future pilot, not publication

The separately pinned model configuration is Qwen3_5, dynamic e4m3 FP8, 128x128 blocks. Existing `repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-eager-server.sh` is historical evidence for TP2, `--quantization fp8 --dtype float16 --kv-cache-dtype auto`, eager, target-only execution and the block-W8A16 gate. Do not execute its old memory/swap or host-operation recipe. Explicit FP16 is required because checkpoint configuration says BF16.

MTP disabled avoids the R314 speculative wider-to-narrower state-width path. It does not erase the separate historical one-token-prefill GDN bug fixed later in R303. The repository rebase result `experiments/qwen38-27b-b70/data/2026-09-12-rebase-v0290-r301-results.json:113` records failures on the old lineage with and without speculation. A future limited worker trial must admit full tokenized prompts strictly greater than one token, preserve the fixed worker SYSTEM and verify that it tokenizes to more than 300 tokens, and test prefill chunk-edge behavior before task requests.

A bounded preregistered correctness check should include the exact worker prompt plus tokenized prompt lengths immediately below, equal to and above the configured prefill batch boundary (for 512-token chunks: 511, 512, 513, and a multi-chunk case with a one-token remainder). Compare final-chunk behavior against an appropriate recorded oracle/control and reject runtime corruption or degenerate output. Do not call superficially fluent output exact correctness. The one-token total-prompt case remains outside the restricted serving contract; no general repair is claimed. No such GPU checks occurred during this audit.
