#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-serial-fa-split-gdn-r50}

"${script_dir}/verify-image-contract.sh" mtp1-serial-fa-split-gdn "${image}"

# XPU Graph variant of the qualified MTP1 strict wrapper for hosts whose
# per-launch submission latency is higher than the publishing host's (see the
# "Independent host replay" section of README.md). Differences from the
# qualified wrapper: VLLM_XPU_ENABLE_XPU_GRAPH=1, cudagraph_mode
# FULL_DECODE_ONLY, capture sizes [1,2] so the MTP1 two-row verification is
# captured too. Not a qualified profile: the c1-c64 identity ladder has not
# been run graph-on; the strict suite outputs matched graph-off MTP0 12/12 on
# the four-B70 replay host.
exec env \
  IMAGE="${image}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:-}" \
  EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD:-1e90ffa672ba02f17a909da11838a4c55b199783}" \
  GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}" \
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
  COMPILATION_CONFIG='{"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2,"inductor_compile_config":{"combo_kernels":false,"benchmark_combo_kernel":false,"deterministic":true,"triton.autotune_pointwise":false,"benchmark_epilogue_fusion":false}}' \
  "${script_dir}/run-w8a16-mtp1-server.sh"
