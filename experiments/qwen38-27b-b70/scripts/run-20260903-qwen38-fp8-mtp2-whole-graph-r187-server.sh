#!/usr/bin/env bash
# Qualified R187 depth-2 profile (mtp2): the R187 mtp1 launcher with num_speculative_tokens=2.
# Strict pair 70.146/70.138 tok/s, 12/12 vs the same-config MTP0 oracle; identity ladder exact through c4 (R187).
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":2}'}
exec env \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp2-whole-graph-r187}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp2-whole-graph-r187}" \
  "${script_dir}/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh"
