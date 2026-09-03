#!/usr/bin/env bash
# Qualified R156 profile (mtp0): the R139 row-invariant image plus the Python
# mixed-step GDN split; same launcher chain as R139 with the split enabled.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export VLLM_XPU_GDN_SPLIT_MIXED=${VLLM_XPU_GDN_SPLIT_MIXED:-1}
export EXPECTED_XPU_OPS_SHA256=${EXPECTED_XPU_OPS_SHA256:-6a7761930cd8b9e3f67902648ba5aaaf708567cebf70fcedda595d698f26b064}
exec env \
  IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-split-mixed-r156}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R156 image ID}" \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp0-split-mixed-r156}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp0-split-mixed-r156}" \
  "${script_dir}/run-20260902-qwen38-fp8-mtp0-fixed-k-r139-server.sh"
