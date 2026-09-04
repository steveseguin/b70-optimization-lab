#!/usr/bin/env bash
# R187 depth-4 profile (mtp4): the R187 mtp1 launcher with num_speculative_tokens=4.
# Strict pair 82.447/82.345 tok/s, 12/12 vs the same-config MTP0 oracle; identity through c16 in two ladders (R197/R201, 2026-09-04).
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":4}'}
exec env \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp4-whole-graph-r187}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp4-whole-graph-r187}" \
  "${script_dir}/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh"
