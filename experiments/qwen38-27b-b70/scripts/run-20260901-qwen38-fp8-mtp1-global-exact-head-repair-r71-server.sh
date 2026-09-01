#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-global-exact-head-repair-r71}

exec env \
  IMAGE="${image}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R71 image ID}" \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-global-exact-r71}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1-global-exact-r71}" \
  MAX_MODEL_LEN="${MAX_MODEL_LEN:-256}" \
  MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}" \
  MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-512}" \
  VLLM_XPU_LM_HEAD_GLOBAL_BATCH_REPAIR_MARGIN="${VLLM_XPU_LM_HEAD_GLOBAL_BATCH_REPAIR_MARGIN:-0.25}" \
  "${script_dir}/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh"
