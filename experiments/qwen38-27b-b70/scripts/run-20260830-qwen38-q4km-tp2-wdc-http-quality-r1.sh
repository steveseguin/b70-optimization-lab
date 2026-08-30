#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
runner=${script_dir}/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh

PROFILE=realistic ARM=control ATTEMPT=1 "${runner}"
PROFILE=realistic ARM=candidate ATTEMPT=1 "${runner}"
PROFILE=concurrency ARM=control ATTEMPT=1 "${runner}"
PROFILE=concurrency ARM=candidate ATTEMPT=1 "${runner}"
PROFILE=concurrency ARM=candidate ATTEMPT=2 "${runner}"
