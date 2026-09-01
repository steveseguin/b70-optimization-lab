#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

export CAMPAIGN_ID=qwen38-tp2-mtp1-decoder-stage-sync-20260831-d64
export CONTAINER_NAME=q38-tp2-mtp1-decoder-stage-sync-d64
export PORT=18365
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-decoder-stage-sync-r1
export TRACE_IMAGE_ID=sha256:a1454ebe9adc227b0dc5eb867c2b9a58ca12cc2594a41c4f070118d6f04cc13c
export RUNTIME_PYTHONPATH=/workspace/vllm:/instrument
export TENSOR_PARALLEL_SIZE=2
export GPU_MASK=0,1
export ONEAPI_SELECTOR=level_zero:0,1
export CONTAINER_MEMORY=13g
export MAX_NUM_BATCHED_TOKENS=256
export ENABLE_PROJECTION_REPAIR=0
export VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=0
export REQUIRE_DUMMY_SAMPLER_STAGE_SYNC=1
export STARTUP_ONLY=1
export SPECULATIVE_CONFIG_JSON='{"method":"qwen3_next_mtp","num_speculative_tokens":1}'
export PREREG_PATH="$script_dir/../notes/2026-08-31-qwen38-tp2-mtp1-decoder-stage-sync-d64-prereg.md"

exec "$script_dir/run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
