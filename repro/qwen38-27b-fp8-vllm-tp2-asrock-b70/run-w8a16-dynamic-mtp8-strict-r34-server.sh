#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Strict singleton qualification profile: MTP8 at one active request. The
# dynamic scheduler retains MTP1 at batch sizes 2-128, but this wrapper fixes a
# one-slot service so no aggregate result can be inferred from this campaign.
exec env \
  IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-dynamic-deterministic-mtp8-r34}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:-sha256:49780a358477b2a49fd25a5f9c317a443e86554680dabed23c789494c1e19e00}" \
  EXPECTED_KERNEL_HEAD="${EXPECTED_KERNEL_HEAD:-1e90ffa672ba02f17a909da11838a4c55b199783}" \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-dynamic-mtp8-strict-r34}" \
  PORT="${PORT:-18134}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-dynamic-mtp8-strict-r34}" \
  MAX_MODEL_LEN=1024 \
  MAX_NUM_SEQS=1 \
  MAX_NUM_BATCHED_TOKENS=1024 \
  SPECULATIVE_CONFIG='{"method":"qwen3_next_mtp","num_speculative_tokens":8,"num_speculative_tokens_per_batch_size":[[1,1,8],[2,128,1]]}' \
  COMPILATION_CONFIG='{"cudagraph_mode":"NONE"}' \
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
