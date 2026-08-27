#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-dynamic-mtp-tp2}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-dynamic-mtp-tp2}
export RUN_ID=${RUN_ID:-qwen38-dynamic-mtp5-package}
export SINGLE_GATE=${SINGLE_GATE:-122.150300}
export C64_GATE=${C64_GATE:-1073.868073}
export REPLICATION_FLOOR=${REPLICATION_FLOOR:-1073.868073}
export QUALITY_PREFIX=${QUALITY_PREFIX:-qwen38-dynamic-mtp5-package-quality}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
