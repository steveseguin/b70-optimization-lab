# Qwen3.6 Quark INT8 RMS+INT8 BF16/FP32 Fusion Rejection

Date: 2026-06-10

## Context

The promoted Qwen3.6 Quark W8A8 INT8 recipe is still the TP4 32K PIECEWISE graph path with clone-safe custom-op all-reduce collectives. Its current single-request baseline is `94.52` output tok/s after first chunk and `93.21` output tok/s end-to-end for p512/n512 streaming completions.

Graph inspection showed the dense path still contains roughly 101 `vllm_ir.rms_norm.default` assignments and roughly 220 `per_token_quant_int8_xpu` assignments. A previous RMS+INT8 fusion attempt did not graph-match because the live Qwen path uses a FP32 transformed norm weight, then casts the RMSNorm output back to BF16 before INT8 quantization.

This candidate changed `csrc/layernorm_quant.cpp` to allow the fused dynamic RMSNorm quant kernel to accept BF16 input plus FP32 weight for INT8 output, with BF16 rounding before scale/quantization.

## Result

Rejected.

The full `setup.py build_ext --inplace` attempt used oneAPI 2026.0 and failed when an unrelated attention target, `paged_decode_xe2.cpp`, was killed by the OS after reaching about 70 GiB RSS and most swap. The patched `_C.abi3.so` did link under `build/temp`, so it was tested directly by copying completed binaries into the local package with backups.

Runtime diagnostics failed before any quality or speed test:

- New `_C` plus rebuilt `_xpu_C`: imports passed, but `torch.ops._xpu_C.per_token_quant_int8_xpu` raised `RuntimeError: Invalid argument` and then aborted the Level Zero runtime.
- New `_C` plus the pre-test June 9 `_xpu_C`: importing `_xpu_C` after `_C` segfaulted.
- New `_C` plus an older import-stable `_xpu_C`: imports passed, but that `_xpu_C` did not expose `per_token_quant_int8_xpu`.
- New `_C` alone: torch XPU reference math completed, then `torch.ops._C.rms_norm_dynamic_per_token_quant` hung on a `1x2048` tensor.

The local package binaries were restored to the pre-test pair, and the running baseline backend/frontdoor `/v1/models` endpoints remained healthy.

## Lesson

This is a stability failure, not a speed candidate. Do not wire this patch into vLLM graph replacement or benchmark it until there is a clean `_C`-only build/test loop with compatible runtime linkage and a direct unit test that completes on a `1x2048` tensor.

Next work should avoid full-extension rebuilds for this kernel loop. If this path is revisited, build only `_C`, keep `_xpu_C` untouched, verify import compatibility first, and validate against the exact graph quant op before graph-pass work.

Artifacts:

- `data/qwen36-quark-int8-rms-int8-bf16fp32-rejected-20260610.json`
- `patches/vllm-xpu-kernels-qwen36-rms-int8-bf16-fp32-rejected-20260610.patch`
