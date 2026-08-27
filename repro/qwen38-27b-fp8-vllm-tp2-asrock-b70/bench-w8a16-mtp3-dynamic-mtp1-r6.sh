#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BASE_URL=${BASE_URL:-http://127.0.0.1:18129}
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-mtp3-dynamic-mtp1-r6}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp3-dynamic-mtp1-r6}
export RUN_ID=${RUN_ID:-qwen38-dynamic-mtp3-r6}
export SINGLE_GATE=${SINGLE_GATE:-85.35379701855078}
export C64_GATE=${C64_GATE:-1063.3382126129186}
export REPLICATION_FLOOR=${REPLICATION_FLOOR:-1063.3382126129186}
export QUALITY_PREFIX=${QUALITY_PREFIX:-qwen38-dynamic-mtp3-r6-quality}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
