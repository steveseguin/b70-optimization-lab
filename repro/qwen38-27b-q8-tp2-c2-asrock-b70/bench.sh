#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../.." && pwd)
source "${script_dir}/../qwen38-27b-q8-tp2-asrock-b70/config.env"

port="${QWEN38_C2_PORT:-18089}"
out="${OUT:-${PWD}/qwen38-q8-tp2-c2.json}"

python3 "${repo_root}/experiments/qwen38-27b-b70/scripts/capture-target-only-c2.py" \
    --base-url "http://${QWEN38_HOST}:${port}" \
    --n-predict 256 \
    --timeout 300 \
    --out "${out}"
