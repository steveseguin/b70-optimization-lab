#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50}

# The qualified control intentionally uses the same final image as MTP1. Only
# speculative decoding is absent, preventing an image-stack mismatch from being
# mistaken for either a speed improvement or an output difference.
"${script_dir}/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${image}"

compilation_config=${COMPILATION_CONFIG:-'{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}'}
exec env \
  IMAGE="${image}" \
  IMAGE_CONTRACT_PROFILE=mtp1-serial-fa-split-gdn \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:-}" \
  EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD:-1e90ffa672ba02f17a909da11838a4c55b199783}" \
  GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}" \
  VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-0}" \
  VLLM_XPU_FP8_BLOCK_W8A16=1 \
  VLLM_BATCH_INVARIANT=0 \
  VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0 \
  VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 \
  VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0 \
  VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 \
  VLLM_XPU_GDN_NATIVE_FALLBACK=1 \
  TORCHINDUCTOR_DETERMINISTIC=1 \
  VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0 \
  VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0 \
  PYTHONHASHSEED=0 \
  CCL_P2P_ACCESS=1 \
  COMPILATION_CONFIG="${compilation_config}" \
  "${script_dir}/run-server.sh"
