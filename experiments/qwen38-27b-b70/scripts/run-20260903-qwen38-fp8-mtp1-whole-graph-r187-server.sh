#!/usr/bin/env bash
# Qualified R187 profile (mtp1): the R156 image and launcher chain with one whole-graph torch.compile
# (COMPILATION_CONFIG splitting_ops=[]) instead of the default piecewise split at the attention/GDN ops.
# XPU graphs stay disabled (VLLM_XPU_ENABLE_XPU_GRAPH=0), so the split had no graph-capture role on this lane;
# the piecewise pipeline was the source of the MTP depth-2 phantom first token (R182-R186, 2026-09-03).
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export COMPILATION_CONFIG=${COMPILATION_CONFIG:-'{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"splitting_ops":[],"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'}
exec env \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-whole-graph-r187}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1-whole-graph-r187}" \
  "${script_dir}/run-20260903-qwen38-fp8-mtp1-split-mixed-r156-server.sh"
