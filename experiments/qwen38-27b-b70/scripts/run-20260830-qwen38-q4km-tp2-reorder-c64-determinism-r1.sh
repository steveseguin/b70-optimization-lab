#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
CAMPAIGN=qwen38-q4km-tp2-reorder-off-c64-determinism-20260830-r1 \
PREREG="${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-reorder-c64-determinism-r1-prereg.json" \
PROFILE=concurrency ARM=control ATTEMPT=1 BASELINE_MODE=1 Q4K_REORDER=0 \
  exec "${script_dir}/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh"
