#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

exec env \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-selective-head-r67}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1-selective-head-r67}" \
  VLLM_XPU_LM_HEAD_BATCH_REPAIR_ROWS=1 \
  "${script_dir}/run-20260901-qwen38-fp8-mtp1-selective-head-batch-repair-r66-server.sh"
