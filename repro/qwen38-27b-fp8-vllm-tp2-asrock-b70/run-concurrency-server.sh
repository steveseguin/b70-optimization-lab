#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}" \
MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}" \
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-256}" \
CCL_P2P_ACCESS="${CCL_P2P_ACCESS:-1}" \
PORT="${PORT:-18089}" \
CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-tp2-concurrency}" \
  exec "${script_dir}/run-server.sh"
