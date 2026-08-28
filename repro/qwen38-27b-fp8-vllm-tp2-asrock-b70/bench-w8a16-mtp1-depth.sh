#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${OUT_DIR:?set OUT_DIR to a new output directory}"

exec env \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1}" \
  OUT_DIR="${OUT_DIR}" \
  "${script_dir}/bench-depth.sh"
