#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export BASE_URL=${BASE_URL:-http://127.0.0.1:18144}
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-mtp8-c2-dynamic-mtp1-r21}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp8-c2-dynamic-mtp1-r21}
export RUN_ID=${RUN_ID:-qwen38-dynamic-mtp8-c2-r21}
export C2_REQUIRE_ORACLE_EXACT=1
export SINGLE_GATE=${SINGLE_GATE:-139.473697}
export C64_GATE=${C64_GATE:-1094.314767}
export REPLICATION_FLOOR=${REPLICATION_FLOOR:-1094.314767}
export QUALITY_PREFIX=${QUALITY_PREFIX:-qwen38-dynamic-mtp8-c2-r21-quality}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
