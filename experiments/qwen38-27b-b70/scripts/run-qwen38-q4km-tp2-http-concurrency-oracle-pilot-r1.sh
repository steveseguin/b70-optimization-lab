#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

PROFILE=tp2 \
CAMPAIGN_ID=qwen38-q4km-tp2-http-concurrency-oracle-pilot-20260825-r1 \
PREREG_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-concurrency-oracle-pilot-prereg.json" \
SUITE_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json" \
HARNESS_REPEATS=1 \
RETURN_TOKEN_IDS=1 \
API_MODE=native \
DISABLE_PROMPT_CACHE=1 \
QUALIFICATION_MODE=isolation \
  exec "${script_dir}/run-qwen38-q4km-tp1-http-smallctx.sh"
