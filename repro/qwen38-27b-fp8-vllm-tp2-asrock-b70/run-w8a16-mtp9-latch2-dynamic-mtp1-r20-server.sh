#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-sd-latch-r2}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:7bd30381b4c57b2a853cf821ef118d1d60b8a27f398f6a263b630c7a04b6b012}
export DYNAMIC_MAMBA_PATCH_SHA256=${DYNAMIC_MAMBA_PATCH_SHA256:-3334c37f33677e4a499aa5959f79fb78d2fa47a39a350ab4bd1a120169512190}
export DYNAMIC_SD_LATCH_PATCH_SHA256=${DYNAMIC_SD_LATCH_PATCH_SHA256:-fe42ed628041032f51cf456ffcc03136f57be9415f34f32354965a655a2b13bf}
export DYNAMIC_SD_LATCH_PEAK_BATCH=${DYNAMIC_SD_LATCH_PEAK_BATCH:-1}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp9-latch2-dynamic-mtp1-r20}
export SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-fp8-w8a16-mtp9-latch2-dynamic-mtp1-r20}
export PORT=${PORT:-18143}
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":9,"num_speculative_tokens_per_batch_size":[[1,1,9],[2,128,1]]}'}

exec "${script_dir}/run-w8a16-mtp2-dynamic-mtp1-fixed-r2-server.sh"
