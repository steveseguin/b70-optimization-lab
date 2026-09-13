#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
PACKAGE_DIR=packages/qwen38-27b-fp8-tp2-b70 LAUNCHER=experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh SERVED_NAME=qwen38-27b-fp8 MODEL_DESC="Qwen/Qwen3.8-27B-FP8" MTP_DEPTH=1 PROFILES="two" \
exec "${repo}/tools/render-container-packet.sh"
