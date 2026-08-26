#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

PROFILE=q8_tp1 \
CAMPAIGN_ID=qwen38-q8-tp1-http-p8-queue-concurrency-20260825-r5 \
PREREG_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp1-http-p8-queue-concurrency-r5-prereg.json" \
SUITE_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-suite.json" \
HARNESS_REPEATS=1 \
RETURN_TOKEN_IDS=1 \
API_MODE=native \
DISABLE_PROMPT_CACHE=1 \
QUALIFICATION_MODE=isolation \
PARALLEL_SLOTS=8 \
CTX_SIZE=4096 \
CONCURRENCY_POINTS=1,2,4,8,16,32,64 \
ALLOW_QUEUEING=1 \
ORACLE_DIGESTS="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp1-http-p8-queue-oracle-digests.json" \
  exec "${script_dir}/run-qwen38-q4km-tp1-http-smallctx.sh"
