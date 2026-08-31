#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)

exec env \
  CAMPAIGN=qwen38-fp8-w8a16-mtp1-c64-batch-invariant-no-combo-20260830-r42 \
  PREREG="${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-fp8-w8a16-mtp1-c64-batch-invariant-no-combo-r42-prereg.json" \
  CONTROL_IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-collective-work-wait-bi-r41 \
  CONTROL_IMAGE_ID=sha256:468026784df774c83b5e1aea18596ccb91a48903ae6e8cc88a414e020a16491c \
  CANDIDATE_IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-bi-r41 \
  CANDIDATE_IMAGE_ID=sha256:bad84355dec6fb70757fd48001df7eebb5e4dd8ef23a1f9d24e338fe663fcec1 \
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false}}' \
  "${script_dir}/run-20260830-qwen38-fp8-w8a16-mtp1-c64-batch-invariant-r40.sh"
