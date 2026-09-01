#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
repro_dir=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
image=${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-compiled-allreduce-custom-op-r60}

exec env \
  IMAGE="${image}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R60 image ID}" \
  EXPECTED_XPU_COMMUNICATOR_SHA256=a959603a21ac4751c63696801a0e4335554db22b14e8f2b4711c392f314dd448 \
  EXPECTED_KERNEL_HEAD=1e90ffa672ba02f17a909da11838a4c55b199783 \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-compiled-allreduce-r60}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1-r60}" \
  MAX_MODEL_LEN="${MAX_MODEL_LEN:-1024}" \
  MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}" \
  MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}" \
  GPU_MEMORY_UTILIZATION=0.95 \
  CONTAINER_MEMORY=12g \
  CONTAINER_MEMORY_SWAP=16g \
  VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1 \
  "${repro_dir}/run-w8a16-mtp1-strict-server.sh"
