# Qwen27 M=4 Fused Post-Attention RMSNorm + W4A16 Prototype

Standalone, default-off experiment for Qwen3.6 27B TP2-local
`M=4, K=5120, N=17408`. It is not imported by or integrated into vLLM.

## Design

The extension exposes one out-variant custom op containing two ordered ESIMD
kernels:

1. Four independent work-groups compute FP16 residual add and effective-gamma
   RMSNorm, producing `residual_out` and `normed_out`.
2. `N` work-groups compute four projections together. Each group reads one
   128-value INT4 weight block once and reuses it across all four M rows.

A single device kernel cannot correctly normalize independent rows and then
launch `N` consumers without a device-wide barrier. The two submissions are
one PyTorch operation and have an explicit SYCL event dependency, making the
operation suitable for `torch.compile` and XPU graph capture while preserving
correctness.

The RMSNorm argument is the effective multiplicative gamma. This matches the
llm-scaler reference's "Gemma-style, w+1 pre-applied" contract. For native
Gemma parameters pass `1 + weight`; Qwen's normal RMSNorm weight is passed
directly.

## AutoRound Layout

No conversion is required after the current INC XPU loader:

- logical `qweight`: INT32 `[K/8,N]`, strides `(1,K/8)`;
- each INT32 stores eight consecutive K values, low nibble first;
- contiguous FP16 `scales`: `[K/128,N]`;
- symmetric effective zero point: 8, so `w=(q-8)*scale`.

The harness demonstrates conversion from checkpoint-contiguous
`qweight[K/8,N]` to the oneDNN NT view with
`qweight.t().contiguous().t()`. The custom kernel and existing oneDNN call then
consume exactly the same tensors.

## Build And Run

Use the same Python/torch environment as the Qwen service, with Intel oneAPI
compiler environment loaded:

```bash
cd /home/steve/llm-optimizations/experiments/qwen27_fused_postattn_rms_w4a16
source /opt/intel/oneapi/compiler/2025.3/env/vars.sh
/home/steve/.venvs/vllm-xpu/bin/python build.py --clean
LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  /home/steve/.venvs/vllm-xpu/bin/python benchmark.py \
  --device xpu:0 --warmup 10 --iterations 50 \
  --json result.json
```

`benchmark.py` refuses to run if TCP port `19448` or `19449` accepts a local
connection. It checks residual/RMS outputs, a memory-bounded dequantized
projection slice, full output parity with `_xpu_C.int4_gemm_w4a16` when that op
is installed, `torch.compile(fullgraph=True)`, and XPU graph replay when the
torch build exposes the graph API.

The harness reports three references: an allocation-heavy eager PyTorch
RMSNorm plus oneDNN projection, projection-only oneDNN, and the production-like
native `_C.fused_add_rms_norm` plus `_xpu_C.int4_gemm_w4a16` path. Only the
last is an appropriate integration gate.

## Reference And Status

Kernel semantics and the vectorized low/high nibble decode follow
`/home/steve/src/llm-scaler` commit
`db05b45831a5a534b74510797832dcf9b3c7e7ab`, file
`vllm/custom-esimd-kernels-vllm/csrc/xpu/esimd_kernels/resadd_norm_gemv_int4.h`.

## Result

Closed as a microbenchmark no-win on 2026-07-11. The extension built with
oneAPI 2025.3 and passed:

- exact residual and normalized activation parity;
- full oneDNN W4A16 output parity (`max_abs=0.015625`,
  `mean_abs=0.0007213`, `RMSE=0.0014940`);
- `torch.compile(fullgraph=True)`;
- one capture plus 1,000 XPU graph replays.

Timing at `M=4, K=5120, N=17408` on B70:

| path | median ms |
|---|---:|
| custom two-kernel fused prototype | `0.206377` |
| eager allocating PyTorch reference + oneDNN | `0.288957` |
| production-like native fused-add RMSNorm + oneDNN | **`0.119454`** |
| oneDNN projection only | `0.107511` |

The apparent win over the eager reference was an unfair baseline. Against the
actual production primitives, the custom path is `72.8%` slower because its
hand-written W4A16 projection cannot match oneDNN. Do not integrate this
kernel. Reopen only if the projection remains oneDNN/DPAS-backed while a larger
boundary is fused without adding a graph split.

Full local result:

`/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-fused-postattn-rms-w4a16-m4-fairbaseline-20260711.json`
