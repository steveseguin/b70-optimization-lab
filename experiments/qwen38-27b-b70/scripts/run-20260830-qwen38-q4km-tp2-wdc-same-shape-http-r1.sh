#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd -- "${script_dir}/../../.." && pwd)
runner=${script_dir}/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh
campaign=qwen38-q4km-tp2-wdc-same-shape-http-20260830-r1
prereg=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-wdc-same-shape-http-r1-prereg.json
realistic_oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-current-control-realistic-oracle.json
concurrency_oracle=${repo}/experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-tp2-current-control-c64-oracle-digests.json

common=(
  CAMPAIGN="${campaign}"
  PREREG="${prereg}"
  BASELINE_MODE=0
  Q4K_REORDER=1
  REALISTIC_ORACLE="${realistic_oracle}"
  EXPECTED_REALISTIC_ORACLE_SHA256=cc2c44acaa8f8ffc8faaf67ddb63a1764f9ad39ad22690db96b9b87ac8b8d6ce
  CONCURRENCY_ORACLE="${concurrency_oracle}"
  EXPECTED_CONCURRENCY_ORACLE_SHA256=eb6ced9b1a86e6324525249f873f7f046aca54eb39e3ce315bf557c21fa0aa5b
)

env "${common[@]}" PROFILE=concurrency ARM=control ATTEMPT=1 "${runner}"
env "${common[@]}" PROFILE=realistic ARM=candidate ATTEMPT=1 "${runner}"
env "${common[@]}" PROFILE=concurrency ARM=candidate ATTEMPT=1 "${runner}"
env "${common[@]}" PROFILE=concurrency ARM=candidate ATTEMPT=2 "${runner}"
