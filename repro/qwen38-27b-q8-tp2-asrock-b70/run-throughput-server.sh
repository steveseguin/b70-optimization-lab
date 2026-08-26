#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

PARALLEL_SLOTS="${PARALLEL_SLOTS:-64}" \
CTX_SIZE="${CTX_SIZE:-32768}" \
THREADS="${THREADS:-8}" \
UBATCH_SIZE="${UBATCH_SIZE:-256}" \
THROUGHPUT_MODE=1 \
MEMORY_HIGH="${MEMORY_HIGH:-11G}" \
MEMORY_MAX="${MEMORY_MAX:-13G}" \
MEMORY_SWAP_MAX="${MEMORY_SWAP_MAX:-12G}" \
  exec "${script_dir}/run-server.sh"
