#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
runner=${script_dir}/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh
out_parent=${OUT_DIR:-/mnt/fast-ai/bench-results}
campaign=qwen38-q4km-tp2-current-control-oracle-20260830-r1
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-current-control-oracle-r1-prereg.json

common=(CAMPAIGN="${campaign}" PREREG="${prereg}" ARM=control)

env "${common[@]}" PROFILE=realistic ATTEMPT=1 BASELINE_MODE=1 "${runner}"
realistic_oracle=${out_parent}/${campaign}-realistic-control-attempt1/realistic-oracle.json
realistic_oracle_sha=$(sha256sum "${realistic_oracle}" | awk '{print $1}')
env "${common[@]}" PROFILE=realistic ATTEMPT=2 BASELINE_MODE=0 \
  REALISTIC_ORACLE="${realistic_oracle}" \
  EXPECTED_REALISTIC_ORACLE_SHA256="${realistic_oracle_sha}" "${runner}"

env "${common[@]}" PROFILE=concurrency ATTEMPT=1 BASELINE_MODE=1 "${runner}"
concurrency_oracle=${out_parent}/${campaign}-concurrency-control-attempt1/oracle-digests.json
concurrency_oracle_sha=$(sha256sum "${concurrency_oracle}" | awk '{print $1}')
env "${common[@]}" PROFILE=concurrency ATTEMPT=2 BASELINE_MODE=0 \
  CONCURRENCY_ORACLE="${concurrency_oracle}" \
  EXPECTED_CONCURRENCY_ORACLE_SHA256="${concurrency_oracle_sha}" "${runner}"
