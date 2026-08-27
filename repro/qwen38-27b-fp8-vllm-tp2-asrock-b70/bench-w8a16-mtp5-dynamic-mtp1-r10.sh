#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BASE_URL=${BASE_URL:-http://127.0.0.1:18133}
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-mtp5-dynamic-mtp1-r10}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp5-dynamic-mtp1-r10}
export RUN_ID=${RUN_ID:-qwen38-dynamic-mtp5-r10}
export SINGLE_GATE=${SINGLE_GATE:-119.045574}
export C64_GATE=${C64_GATE:-1069.819138}
export REPLICATION_FLOOR=${REPLICATION_FLOOR:-1069.819138}
export QUALITY_PREFIX=${QUALITY_PREFIX:-qwen38-dynamic-mtp5-r10-quality}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
