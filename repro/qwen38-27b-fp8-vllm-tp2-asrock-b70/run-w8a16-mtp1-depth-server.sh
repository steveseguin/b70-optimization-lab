#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Qualified R33 exact-depth profile. Caller-selected model/cache paths remain
# portable; changing capacity, topology, quantization, or speculation creates a
# different profile.
exec env \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-depth-tp2}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1}" \
  MAX_MODEL_LEN=33024 \
  MAX_NUM_SEQS=1 \
  MAX_NUM_BATCHED_TOKENS=4096 \
  "${script_dir}/run-w8a16-mtp1-strict-server.sh"
