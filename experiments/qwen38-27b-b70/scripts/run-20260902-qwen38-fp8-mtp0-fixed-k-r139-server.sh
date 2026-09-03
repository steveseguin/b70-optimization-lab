#!/usr/bin/env bash
# Qualified R139 MTP0 profile: same row-invariant fixed-K W8A16 image, no
# speculative decoding. Matched-image control for the MTP1 profile and the
# published target-only baseline.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
repro_dir=${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70
export EXPECTED_XPU_EXTENSION_SHA256=${EXPECTED_XPU_EXTENSION_SHA256:-f912e12de1d79206221142c9a50af2aba70d2c77c735c9cd2d5d8d9def0740d1}
exec env \
  IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R139 image ID}" \
  EXPECTED_KERNEL_HEAD=1e90ffa672ba02f17a909da11838a4c55b199783 \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp0-fixed-k-r139}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp0-fixed-k-r139}" \
  MAX_MODEL_LEN="${MAX_MODEL_LEN:-1024}" \
  MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}" \
  MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}" \
  CONTAINER_MEMORY="${CONTAINER_MEMORY:-12g}" \
  CONTAINER_MEMORY_SWAP="${CONTAINER_MEMORY_SWAP:-16g}" \
  "${repro_dir}/${STRICT_WRAPPER:-run-w8a16-mtp0-strict-server.sh}"
