#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
repro_dir=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-draft-only-int4-r62}

exec env \
  IMAGE="${image}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R62 image ID}" \
  EXPECTED_KERNEL_HEAD=1e90ffa672ba02f17a909da11838a4c55b199783 \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-draft-int4-r62}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1-draft-int4-r62}" \
  MAX_MODEL_LEN="${MAX_MODEL_LEN:-1024}" \
  MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}" \
  MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}" \
  GPU_MEMORY_UTILIZATION=0.95 \
  CONTAINER_MEMORY=12g \
  CONTAINER_MEMORY_SWAP=16g \
  VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
  VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 \
  VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 \
  VLLM_XPU_DRAFT_LM_HEAD_INT4_CHUNK_ROWS=2048 \
  "${repro_dir}/${STRICT_WRAPPER:-run-w8a16-mtp1-strict-server.sh}"
