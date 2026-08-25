#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

CAMPAIGN_ID=qwen38-q4km-tp1-http-concurrency-20260825-r3 \
PREREG_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-concurrency-r3-prereg.json" \
HARNESS_REPEATS=1 \
RETURN_TOKEN_IDS=1 \
API_MODE=native \
DISABLE_PROMPT_CACHE=1 \
QUALIFICATION_MODE=isolation \
ORACLE_DIGESTS="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-concurrency-oracle-digests.json" \
  exec "${script_dir}/run-qwen38-q4km-tp1-http-smallctx.sh"
