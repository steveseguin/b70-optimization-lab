#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BASE_URL=${BASE_URL:-http://127.0.0.1:18137}
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-mtp7-dynamic-mtp1-r14}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp7-dynamic-mtp1-r14}
export RUN_ID=${RUN_ID:-qwen38-dynamic-mtp7-r14}
export SINGLE_GATE=${SINGLE_GATE:-131.839661}
export C64_GATE=${C64_GATE:-1079.162716}
export REPLICATION_FLOOR=${REPLICATION_FLOOR:-1079.162716}
export QUALITY_PREFIX=${QUALITY_PREFIX:-qwen38-dynamic-mtp7-r14-quality}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
