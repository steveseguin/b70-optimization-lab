#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-sd-latch-r1}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:312c501233ab61bca2642a4412a338baf054951b14feb39a1ad18fa5c104af86}
export DYNAMIC_MAMBA_PATCH_SHA256=${DYNAMIC_MAMBA_PATCH_SHA256:-3334c37f33677e4a499aa5959f79fb78d2fa47a39a350ab4bd1a120169512190}
export DYNAMIC_SD_LATCH_PATCH_SHA256=${DYNAMIC_SD_LATCH_PATCH_SHA256:-e15287dc97b448bc067ef7d2aa71cf2855a754ff621573470e4d643c54c7ca64}
export DYNAMIC_SD_LATCH_PEAK_BATCH=${DYNAMIC_SD_LATCH_PEAK_BATCH:-1}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp9-latch-dynamic-mtp1-r19}
export SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-fp8-w8a16-mtp9-latch-dynamic-mtp1-r19}
export PORT=${PORT:-18142}
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":9,"num_speculative_tokens_per_batch_size":[[1,1,9],[2,128,1]]}'}

exec "${script_dir}/run-w8a16-mtp2-dynamic-mtp1-fixed-r2-server.sh"
