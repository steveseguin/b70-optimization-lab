#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp7-dynamic-mtp1-r14}
export SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-fp8-w8a16-mtp7-dynamic-mtp1-r14}
export PORT=${PORT:-18137}

exec "${script_dir}/run-w8a16-mtp7-dynamic-mtp1-r13-server.sh"
