#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp3-dynamic-mtp1-r7}
export SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-fp8-w8a16-mtp3-dynamic-mtp1-r7}
export PORT=${PORT:-18130}

exec "${script_dir}/run-w8a16-mtp3-dynamic-mtp1-r6-server.sh"
