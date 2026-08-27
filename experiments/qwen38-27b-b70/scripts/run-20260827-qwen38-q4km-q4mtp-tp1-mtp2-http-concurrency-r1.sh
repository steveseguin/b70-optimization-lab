#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

CAMPAIGN_ID=qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-20260827-r1 \
PREREG_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-http-concurrency-r1-prereg.json" \
PROFILE=q4mtp2_tp1 \
HARNESS_REPEATS=1 \
RETURN_TOKEN_IDS=1 \
API_MODE=native \
DISABLE_PROMPT_CACHE=1 \
QUALIFICATION_MODE=isolation \
ORACLE_DIGESTS="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-concurrency-oracle-digests.json" \
PARALLEL_SLOTS=64 \
CTX_SIZE=32768 \
CONCURRENCY_POINTS=1,2,4,8,16,32,64 \
CONCURRENT_CANARY=1 \
CANARY_CONCURRENCY=64 \
CANARY_ROUNDS=2 \
  exec "${script_dir}/run-qwen38-q4km-tp1-http-smallctx.sh"
