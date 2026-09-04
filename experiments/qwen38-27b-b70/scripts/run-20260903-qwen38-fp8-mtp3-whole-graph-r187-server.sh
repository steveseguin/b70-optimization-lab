#!/usr/bin/env bash
# R187 depth-3 profile (mtp3): the R187 mtp1 launcher with num_speculative_tokens=3.
# Strict pair 79.163/79.203 tok/s, 12/12 vs the same-config MTP0 oracle (R191, 2026-09-03).
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":3}'}
exec env \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp3-whole-graph-r187}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp3-whole-graph-r187}" \
  "${script_dir}/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh"
