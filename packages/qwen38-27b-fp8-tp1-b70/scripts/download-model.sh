#!/usr/bin/env bash
# Download the exact pinned Qwen3.8-27B-FP8 weights this package serves (same files as the two-card package).
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); repo=$(cd -- "${here}/../../.." && pwd)
export MODEL_MANIFEST=${MODEL_MANIFEST:-${repo}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json}
exec "${repo}/tools/container-packet/download-model.sh" "$@"
