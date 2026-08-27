#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-dynamic-mtp-tp2}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-dynamic-mtp-tp2}
export RUN_ID=${RUN_ID:-qwen38-dynamic-mtp8-package}
export SINGLE_GATE=${SINGLE_GATE:-139.473697}
export C64_GATE=${C64_GATE:-1072.428472}
export REPLICATION_FLOOR=${REPLICATION_FLOOR:-1072.428472}
export QUALITY_PREFIX=${QUALITY_PREFIX:-qwen38-dynamic-mtp8-package-quality}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
