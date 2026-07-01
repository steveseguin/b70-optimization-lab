# vLLM XPU Kernels `_C`-Only Build Loop

Date: 2026-06-10

The rejected Qwen3.6 RMS+INT8 fusion attempt exposed a build-loop problem: `setup.py build_ext --inplace` always targets `_C`, `_vllm_fa2_C`, `_moe_C`, `_xpu_C`, and `xpumem_allocator`. Even for a small `csrc/layernorm_quant.cpp` edit, that path dragged in unrelated attention code and was killed while compiling `paged_decode_xe2.cpp`.

I validated a direct CMake path that builds only `_C`:

```bash
KERNELS_DIR=/home/steve/src/vllm-xpu-kernels \
VENV_DIR=/home/steve/.venvs/vllm-xpu \
ONEAPI_VARS=/opt/intel/oneapi/compiler/2025.3/env/vars.sh \
AOT_DEVICES=bmg-g21-a0 \
JOBS=4 \
CLEAN=1 \
scripts/build-vllm-xpu-kernels-c-only.sh
```

Result:

- Configured with only `BASIC_KERNELS_ENABLED=ON`.
- Disabled FA2, MoE, GDN, MQA logits, `_xpu_C`, xpumem allocator, XE default, XE2 TLA, and non-basic kernels.
- Built 15 `_C` steps successfully.
- Installed `/tmp/vllm-xpu-c-only-2025/vllm_xpu_kernels/_C.abi3.so`.
- Imported the temp `_C` under oneAPI 2025.3 and confirmed `torch.ops._C.rms_norm_dynamic_per_token_quant` is registered.

Use this loop for future exact fused-kernel work. Do not use full `setup.py build_ext --inplace` for `_C`-only iteration unless a full package rebuild is intentionally needed.
