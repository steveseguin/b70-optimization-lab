#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

MAX_MODEL_LEN="${MAX_MODEL_LEN:-33024}" \
MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}" \
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-4096}" \
PORT="${PORT:-18088}" \
CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-tp2-depth}" \
  exec "${script_dir}/run-server.sh"
