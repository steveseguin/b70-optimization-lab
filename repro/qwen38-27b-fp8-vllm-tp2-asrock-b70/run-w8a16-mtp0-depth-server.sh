#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# Matched-image MTP0 oracle for the real-content depth matrix. Keep the final
# R50 image and deterministic compiler contract identical to MTP1; only the
# speculative decoder is absent.
exec env \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp0-depth-tp2}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp0-depth}" \
  MAX_MODEL_LEN=33024 \
  MAX_NUM_SEQS=1 \
  MAX_NUM_BATCHED_TOKENS=4096 \
  "${script_dir}/run-w8a16-mtp0-strict-server.sh"
