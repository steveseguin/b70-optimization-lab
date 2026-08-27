#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BASE_URL=${BASE_URL:-http://127.0.0.1:18131}
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-mtp4-dynamic-mtp1-r8}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp4-dynamic-mtp1-r8}
export RUN_ID=${RUN_ID:-qwen38-dynamic-mtp4-r8}
export SINGLE_GATE=${SINGLE_GATE:-101.929043}
export C64_GATE=${C64_GATE:-1053.441141}
export REPLICATION_FLOOR=${REPLICATION_FLOOR:-1053.441141}
export QUALITY_PREFIX=${QUALITY_PREFIX:-qwen38-dynamic-mtp4-r8-quality}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
