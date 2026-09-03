#!/usr/bin/env bash
# R154: plain R139 image with no static compile size (compile_sizes []), ladders only.
set -uo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=/mnt/fast-ai/bench-results/qwen38-fp8-compile-sizes-ladders-20260903-r154 \
IMAGE_OVERRIDE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139 \
IMAGE_ID_OVERRIDE=sha256:901ae9e0ade0109e94dd162d0cf2c398440325b1791f3191376fa0013dc29878 \
LAYERNORM_SHA256_OVERRIDE=50cf5f4f9c72f679e4318cd3e3e021a844f59ac188a891d9a4f9638188f4bce8 \
GEMMA_TRITON=0 RMSNORM_TRITON=0 LADDERS_ONLY=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"compile_sizes":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' \
  "${script_dir}/run-20260902-qwen38-fp8-triton-rmsnorm-r152.sh"
