#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

export CAMPAIGN_ID=qwen38-tp2-mtp1-profile-only-strict-20260831-d68
export CONTAINER_NAME=q38-tp2-mtp1-profile-only-strict-d68
export PORT=18369
export TRACE_IMAGE=neural-download/vllm-openai-xpu:qwen38-autoround-profile-only-decoder-sync-r1
export TRACE_IMAGE_ID=sha256:e28eaf37226390f3371ec67cf7e45737ee94849fce54237c260831194280fdfb
export RUNTIME_PYTHONPATH=/workspace/vllm:/instrument
export TENSOR_PARALLEL_SIZE=2
export GPU_MASK=0,1
export ONEAPI_SELECTOR=level_zero:0,1
export CONTAINER_MEMORY=13g
export MAX_NUM_BATCHED_TOKENS=256
export ENABLE_PROJECTION_REPAIR=1
export VLLM_XPU_QWEN38_PREFILL_PROJECTION_SYNCHRONIZE=0
export VLLM_XPU_QWEN38_PREFILL_SMALL_PAD_TOKENS=512
export REQUIRE_DUMMY_SAMPLER_STAGE_SYNC=1
export DUMMY_SAMPLER_RUNS_PER_RANK=2
export EXPECTED_DECODER_STAGE_RECEIPTS=1040
export STARTUP_ONLY=0
export SPECULATIVE_CONFIG_JSON='{"method":"qwen3_next_mtp","num_speculative_tokens":1}'
export REFERENCE_PERFORMANCE=/mnt/fast-ai/bench-results/qwen38-prefill-projection-repair-tp2-strict-20260831-d59r/performance.json
export PREREG_PATH="$script_dir/../notes/2026-08-31-qwen38-tp2-mtp1-profile-only-strict-d68-prereg.md"

exec "$script_dir/run-20260831-qwen38-prefill-projection-repair-strict-d54.sh"
