#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export CAMPAIGN_ID=qwen38-prefill-projection-repair-nosync-strict-20260831-d57
export CONTAINER_NAME=q38-prefill-projection-repair-nosync-d57
export PORT=18357
export VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=0
export PREREG_PATH="$script_dir/../notes/2026-08-31-qwen38-prefill-projection-repair-nosync-strict-d57-prereg.md"
export REFERENCE_PERFORMANCE=/mnt/fast-ai/bench-results/qwen38-prefill-projection-repair-strict-20260831-d54/performance.json
exec "$script_dir/run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
