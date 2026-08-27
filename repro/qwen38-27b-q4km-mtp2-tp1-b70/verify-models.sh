#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../.." && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR to the directory containing Qwen3.8-27B-Q4_K_M.gguf}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR to the directory containing mtp-Qwen3.8-27B-Q4_0.gguf}
python3 "${repo}/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "${repo}/repro/qwen38-27b-q4km-tp1-b70/model-direct.json" "${target_dir}" "$@"
python3 "${repo}/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "${script_dir}/draft-model-direct.json" "${draft_dir}" "$@"
