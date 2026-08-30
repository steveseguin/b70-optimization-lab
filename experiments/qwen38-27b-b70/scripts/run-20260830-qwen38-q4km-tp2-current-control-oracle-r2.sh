#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
CAMPAIGN=qwen38-q4km-tp2-current-control-oracle-20260830-r2 \
PREREG="${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-current-control-oracle-r2-prereg.json" \
  exec "${script_dir}/run-20260830-qwen38-q4km-tp2-current-control-oracle-r1.sh"
