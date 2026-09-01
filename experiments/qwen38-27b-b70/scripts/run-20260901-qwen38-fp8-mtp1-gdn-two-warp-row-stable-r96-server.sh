#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

exec env \
  IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-two-warp-row-stable-r96}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R96 image ID}" \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-mtp1-gdn-two-warp-row-stable-r96}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-mtp1-gdn-two-warp-row-stable-r96}" \
  MAX_MODEL_LEN="${MAX_MODEL_LEN:-256}" \
  MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}" \
  MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-512}" \
  VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  VLLM_XPU_GDN_ISOLATE_QKVZ_PREFILL_REQUESTS=1 \
  VLLM_XPU_GDN_ISOLATE_PREFILL_REQUESTS=1 \
  VLLM_XPU_GDN_ROW_STABLE_RMSNORM=1 \
  "${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh"
