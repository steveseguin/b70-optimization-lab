#!/usr/bin/env bash
# Qualified R139 profile: row-invariant fixed-K W8A16 kernel image with the
# R62 draft-only INT4 treatment (target verifier FP16). Same launcher chain
# as R62; only the image, its expected ID, and the extension digest change.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export EXPECTED_XPU_EXTENSION_SHA256=${EXPECTED_XPU_EXTENSION_SHA256:-f912e12de1d79206221142c9a50af2aba70d2c77c735c9cd2d5d8d9def0740d1}
exec env \
  IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-fixed-k-w8a16-r139}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R139 image ID}" \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-w8a16-mtp1-fixed-k-r139}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-block-w8a16-mtp1-fixed-k-r139}" \
  "${script_dir}/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh"
