#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

PROFILE=q8 \
CAMPAIGN_ID=qwen38-q8-tp2-http-depth-prefill-20260825-r3 \
PREREG_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp2-http-depth-prefill-r3-prereg.json" \
  exec "${script_dir}/run-qwen38-q4km-tp2-http-depth-r1.sh"
