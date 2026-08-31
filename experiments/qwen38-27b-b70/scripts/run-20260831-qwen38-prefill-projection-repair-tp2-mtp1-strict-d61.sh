#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export CAMPAIGN_ID=qwen38-prefill-projection-repair-tp2-mtp1-strict-20260831-d61
export CONTAINER_NAME=q38-prefill-projection-repair-tp2-mtp1-d61
export PORT=18362
export TENSOR_PARALLEL_SIZE=2
export GPU_MASK=0,1
export ONEAPI_SELECTOR=level_zero:0,1
export CONTAINER_MEMORY=13g
export MAX_NUM_BATCHED_TOKENS=256
export VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=0
export VLLM_XPU_QWEN38_PREFILL_SMALL_PAD_TOKENS=512
export SPECULATIVE_CONFIG_JSON='{"method":"qwen3_next_mtp","num_speculative_tokens":1}'
export PREREG_PATH="$script_dir/../notes/2026-08-31-qwen38-prefill-projection-repair-tp2-mtp1-strict-d61-prereg.md"
export REFERENCE_PERFORMANCE=/mnt/fast-ai/bench-results/qwen38-prefill-projection-repair-tp2-strict-20260831-d59r/performance.json
exec "$script_dir/run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
