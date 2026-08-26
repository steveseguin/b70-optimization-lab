#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)

PILOT=0 \
CAMPAIGN_ID=qwen38-fp8-tp2-http-concurrency-20260826-r2 \
PREREG_PATH="${repo_root}/experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-concurrency-r2-prereg.json" \
ORACLE_DIGESTS="${repo_root}/experiments/qwen38-27b-b70/data/qwen38-fp8-tp2-http-concurrency-oracle-pilot-20260826-r1-attempt1/oracle-digests.json" \
  exec "${script_dir}/run-qwen38-fp8-tp2-http-concurrency-r1.sh"
