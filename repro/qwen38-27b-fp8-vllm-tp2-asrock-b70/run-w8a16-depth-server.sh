#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-block-w8a16-20260826}" \
VLLM_XPU_FP8_BLOCK_W8A16=1 \
MAX_MODEL_LEN="${MAX_MODEL_LEN:-33024}" \
MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}" \
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-4096}" \
CCL_P2P_ACCESS="${CCL_P2P_ACCESS:-0}" \
PORT="${PORT:-18119}" \
CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-block-w8a16-tp2-depth}" \
  exec "${script_dir}/run-server.sh"
