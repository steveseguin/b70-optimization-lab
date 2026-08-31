#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export CAMPAIGN_ID=qwen38-prefill-projection-repair-tp2-strict-replay-20260831-d60
export CONTAINER_NAME=q38-prefill-projection-repair-tp2-d60
export PORT=18361
export TENSOR_PARALLEL_SIZE=2
export GPU_MASK=0,1
export ONEAPI_SELECTOR=level_zero:0,1
export CONTAINER_MEMORY=13g
export MAX_NUM_BATCHED_TOKENS=256
export VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=0
export VLLM_XPU_QWEN38_PREFILL_SMALL_PAD_TOKENS=512
export PREREG_PATH="$script_dir/../notes/2026-08-31-qwen38-prefill-projection-repair-tp2-strict-d60-prereg.md"
export REFERENCE_PERFORMANCE=/mnt/fast-ai/bench-results/qwen38-prefill-projection-repair-tp2-strict-20260831-d59r/performance.json
exec "$script_dir/run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
