#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
arm="${CAPACITY_ARM:-p32-k16}"

case "${arm}" in
  p32-k16)
    parallel_slots=32
    ctx_size=16384
    concurrency_points=1,2,4,8,16,32
    ;;
  p16-k8)
    parallel_slots=16
    ctx_size=8192
    concurrency_points=1,2,4,8,16
    ;;
  p8-k4)
    parallel_slots=8
    ctx_size=4096
    concurrency_points=1,2,4,8
    ;;
  *)
    printf 'FAIL: CAPACITY_ARM must be p32-k16, p16-k8, or p8-k4\n' >&2
    exit 1
    ;;
esac

PROFILE=q8_tp1 \
CAMPAIGN_ID="qwen38-q8-tp1-http-capacity-${arm}-20260825-r2" \
PREREG_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp1-http-capacity-oracle-pilot-r2-prereg.json" \
SUITE_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-smallctx-suite.json" \
HARNESS_REPEATS=1 \
RETURN_TOKEN_IDS=1 \
API_MODE=native \
DISABLE_PROMPT_CACHE=1 \
QUALIFICATION_MODE=isolation \
PARALLEL_SLOTS="${parallel_slots}" \
CTX_SIZE="${ctx_size}" \
CONCURRENCY_POINTS="${concurrency_points}" \
  exec "${script_dir}/run-qwen38-q4km-tp1-http-smallctx.sh"
