#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Qualified r32 configuration. Keep this wrapper explicit: changing any of
# these values creates a new, unqualified deployment profile.
exec env \
  IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-rms-serial-r31}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:-sha256:ba42e928e69c60d1c9102df6ec1c0e998e9dd8463f74d5dc0a8b4bb45108fa9b}" \
  EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD:-1e90ffa672ba02f17a909da11838a4c55b199783}" \
  ENFORCE_EAGER=0 \
  VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  VLLM_XPU_FP8_BLOCK_W8A16=1 \
  VLLM_BATCH_INVARIANT=0 \
  VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=0 \
  VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 \
  VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0 \
  VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1 \
  VLLM_XPU_GDN_NATIVE_FALLBACK=1 \
  VLLM_XPU_MTP_SUPPRESS_BONUS_TOKEN=0 \
  VLLM_XPU_MTP_DRAFT_EAGER=0 \
  TORCHINDUCTOR_DETERMINISTIC=1 \
  "${script_dir}/run-w8a16-mtp1-server.sh"
