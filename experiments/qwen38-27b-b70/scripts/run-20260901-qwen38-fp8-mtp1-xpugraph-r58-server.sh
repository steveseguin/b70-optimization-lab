#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
repro_dir=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50-reprocheck-r55c}

"${repro_dir}/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${image}"

# R58 changes exactly one qualified R56 runtime variable: XPU Graph off -> on.
exec env \
  IMAGE="${image}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:-sha256:41aec5da9b124497a9b5dbc6b38f17175bf923d930d5702b9913589f107802d4}" \
  EXPECTED_KERNEL_HEAD=1e90ffa672ba02f17a909da11838a4c55b199783 \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-xpugraph-r58}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1}" \
  MAX_MODEL_LEN=33024 \
  MAX_NUM_SEQS=1 \
  MAX_NUM_BATCHED_TOKENS=4096 \
  GPU_MEMORY_UTILIZATION=0.95 \
  CONTAINER_MEMORY=12g \
  CONTAINER_MEMORY_SWAP=16g \
  ENFORCE_EAGER=0 \
  VLLM_XPU_ENABLE_XPU_GRAPH=1 \
  VLLM_XPU_FP8_BLOCK_W8A16=1 \
  VLLM_XPU_FP8_PACKED_SERIAL_EXACT=0 \
  VLLM_XPU_FA_SERIAL_SPEC_DECODE=0 \
  VLLM_XPU_FA_SERIAL_SPEC_NO_CAUSAL=0 \
  VLLM_BATCH_INVARIANT=0 \
  VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0 \
  VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 \
  VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0 \
  VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT=0 \
  VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT=0 \
  VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 \
  VLLM_XPU_GDN_NATIVE_FALLBACK=1 \
  VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN=0 \
  VLLM_XPU_MTP_DRAFT_EAGER=0 \
  TORCHINDUCTOR_DETERMINISTIC=1 \
  VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE=0 \
  VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING=0 \
  PYTHONHASHSEED=0 \
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' \
  "${repro_dir}/run-w8a16-mtp1-server.sh"
