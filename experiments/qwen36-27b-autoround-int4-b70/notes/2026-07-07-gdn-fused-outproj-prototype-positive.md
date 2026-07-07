# Qwen27 GDN fused norm/gate + INT4 out-proj prototype

Date: 2026-07-07

## Status

Diagnostic prototype is buildable, importable, parity-smoke clean, and
synthetic microbench-positive. It is **not** wired into the endpoint yet and is
not a LocalMaxxing / headline throughput result.

## Why this was tried

The current valid Qwen27 record is still the strict fresh-response
`68.23626314761921 tok/s` row for the webhie AutoRound INT4 checkpoint with
runtime INT8 target LM-head BF16 scales, runtime INT4 draft LM-head BF16
scales, MTP3, ReplaySSM exact GDN state, and conservative PyTorch slot fallback.

Previous small GDN body fusions were no-win at endpoint scale, but this target
is different: it fuses the GDN output-side gated RMSNorm workspace creation
directly into the INT4 W4A16 `out_proj` input path. That removes several
per-layer wrapper/pointwise operations before the existing oneDNN INT4 GEMM.

## Patch artifacts

- XPU kernel prototype:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-qwen27-gdn-fused-outproj-prototype-20260707.patch`
- vLLM fake-registration hunk:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-gdn-fused-outproj-fake-reg-20260707.patch`
- Structured diagnostic:
  `experiments/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-gdn-fused-outproj-prototype-microbench-20260707.json`

The live runtime was **not** overwritten. The built test binary is:

`/tmp/vllm-xpu-20260707-gdn-fused-outproj/vllm_xpu_kernels/_xpu_C.abi3.so`

## Build and import

Build command used oneAPI 2025.3 / sycl8-compatible runtime:

```bash
cd /home/steve/src/vllm-xpu-kernels
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
source /home/steve/.venvs/vllm-xpu/bin/activate
export VLLM_XPU_AOT_DEVICES=bmg-g21-a0
export VLLM_XPU_XE2_AOT_DEVICES=bmg-g21-a0
cmake --build build/20260707-gdn-fused-outproj -j=8 --target _xpu_C
cmake --install build/20260707-gdn-fused-outproj \
  --prefix /tmp/vllm-xpu-20260707-gdn-fused-outproj --component _xpu_C
```

Import check loaded the temporary module and registered:

`torch.ops._xpu_C.qwen_gdn_out_proj_int4_w4a16`

Important runtime detail: PyTorch XPU saw zero devices until the launcher-style
library path included the venv lib and torch lib directories:

```bash
export LD_LIBRARY_PATH="/tmp/vllm-xpu-20260707-gdn-fused-outproj/vllm_xpu_kernels:/home/steve/src/vllm-xpu-kernels/build/20260707-gdn-fused-outproj:/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
```

## Correctness smoke

Reference path:

1. PyTorch BF16/FP16 gated RMSNorm workspace:
   `core * rsqrt(mean(core^2) + eps) * norm_weight * silu(z)`;
2. reshape to `[T, H * D]`;
3. existing `_xpu_C.int4_gemm_w4a16`.

Fused path:

`_xpu_C.qwen_gdn_out_proj_int4_w4a16(core, z, norm_weight, qweight, bias, scales, qzeros, group_size, eps)`

Synthetic small-shape parity passed for both FP16 and BF16 with `max_abs=0`.

## Synthetic full-shape microbench

Shape matched the Qwen27 GDN out-proj local subpath:

- `heads=48`;
- `head_dim=128`;
- input K = `6144`;
- output N = `5120`;
- `group_size=128`;
- BF16 activation/scales;
- symmetric zero point `[8]`;
- random packed INT4 weights.

Rows:

| tokens | reference ms | fused ms | speedup | max abs |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0.20761 | 0.04158 | 4.99x | 0.001953 |
| 2 | 0.21108 | 0.03482 | 6.06x | 0 |
| 4 | 0.20749 | 0.03114 | 6.66x | 0 |
| 8 | 0.20778 | 0.03092 | 6.72x | 0.000977 |

This is a diagnostic subpath result only. It may overstate endpoint impact
because endpoint graph capture, wrapper scheduling, and real quantized layer
objects can change the bottleneck. Still, the magnitude is large enough to
justify a default-off endpoint integration screen.

## Next action

Wire the op into `GatedDeltaNetAttention` behind a default-off env flag for
TP1 INC W4A16 `out_proj` only. Required guards:

- XPU only;
- TP1 first;
- `core_attn_out` / `z` contiguous `[T, H, 128]`;
- norm is the Qwen GDN `RMSNormGated` / `norm_before_gate=True` path;
- `out_proj` exposes GPTQ/INC packed INT4 weight, BF16/FP16 scales, symmetric
  zero point, and `group_size=128`;
- no logprobs/sampling semantic change; this only replaces a hidden-state
  projection before normal target verification.

Endpoint validation rule:

1. first run a strict fresh realistic-suite speed screen with quality skipped;
2. if it beats same-window controls by more than variance, run repeat64 quality
   and baseline-match checks;
3. only then promote, document as a real result, and consider LocalMaxxing.

