#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
target_dir=${TARGET_DIR:?set TARGET_DIR to the directory containing Qwen3.8-27B-Q8_0.gguf}
draft_dir=${DRAFT_DIR:?set DRAFT_DIR to the directory containing mtp-Qwen3.8-27B-Q4_0.gguf}

"${repo}/repro/qwen38-27b-q8-tp1-b70/verify-model-direct.sh" "${target_dir}"
python3 "${repo}/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py" \
  "${repo}/repro/qwen38-27b-q4km-mtp2-tp1-b70/draft-model-direct.json" "${draft_dir}"
