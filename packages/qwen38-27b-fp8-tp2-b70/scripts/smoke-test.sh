#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
export PACKAGE_DIR=packages/qwen38-27b-fp8-tp2-b70 SERVED_NAME=qwen38-27b-fp8 PACKET_NAME="Qwen/Qwen3.8-27B-FP8 B70 packet" MODEL_GIB=28
exec "${repo}/tools/container-packet/smoke-test.sh" "$@"
