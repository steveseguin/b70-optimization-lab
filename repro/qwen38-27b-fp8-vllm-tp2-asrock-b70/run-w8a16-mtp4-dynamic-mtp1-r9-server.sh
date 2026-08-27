#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp4-dynamic-mtp1-r9}
export SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-fp8-w8a16-mtp4-dynamic-mtp1-r9}
export PORT=${PORT:-18132}

exec "${script_dir}/run-w8a16-mtp4-dynamic-mtp1-r8-server.sh"
