#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export MODEL_NAME=${MODEL_NAME:-qwen38-fp8-w8a16-dynamic-mtp-tp2}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-dynamic-mtp-tp2}

exec "${script_dir}/bench-w8a16-mtp2-dynamic-mamba-r5.sh"
