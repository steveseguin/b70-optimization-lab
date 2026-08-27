#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export IMAGE=${IMAGE:-neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1}
export EXPECTED_IMAGE_ID=${EXPECTED_IMAGE_ID:-sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6}
export DYNAMIC_MAMBA_PATCH_SHA256=${DYNAMIC_MAMBA_PATCH_SHA256:-3334c37f33677e4a499aa5959f79fb78d2fa47a39a350ab4bd1a120169512190}
export CONTAINER_NAME=${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp7-dynamic-mtp1-r13}
export SERVED_MODEL_NAME=${SERVED_MODEL_NAME:-qwen38-fp8-w8a16-mtp7-dynamic-mtp1-r13}
export PORT=${PORT:-18136}
export SPECULATIVE_CONFIG=${SPECULATIVE_CONFIG:-'{"method":"qwen3_next_mtp","num_speculative_tokens":7,"num_speculative_tokens_per_batch_size":[[1,1,7],[2,128,1]]}'}

exec "${script_dir}/run-w8a16-mtp2-dynamic-mtp1-fixed-r2-server.sh"
