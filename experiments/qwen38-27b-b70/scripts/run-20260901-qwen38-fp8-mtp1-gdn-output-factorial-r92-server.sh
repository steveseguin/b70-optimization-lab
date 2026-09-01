#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "${script_dir}/../../.." && pwd)
variant=${R92_VARIANT:?set R92_VARIANT to norm or projection}

case "${variant}" in
  norm)
    norm_gate=1
    projection_gate=0
    ;;
  projection)
    norm_gate=0
    projection_gate=1
    ;;
  *)
    printf 'R92_VARIANT must be norm or projection\n' >&2
    exit 2
    ;;
esac

exec env \
  IMAGE="${IMAGE:-neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-gdn-output-factorial-r92}" \
  EXPECTED_IMAGE_ID="${EXPECTED_IMAGE_ID:?set EXPECTED_IMAGE_ID to the locally built R92 image ID}" \
  CONTAINER_NAME="${CONTAINER_NAME:-qwen38-fp8-mtp1-gdn-output-r92-${variant}}" \
  PORT="${PORT:-18124}" \
  SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen38-fp8-mtp1-gdn-output-r92-${variant}}" \
  MAX_MODEL_LEN="${MAX_MODEL_LEN:-256}" \
  MAX_NUM_SEQS="${MAX_NUM_SEQS:-64}" \
  MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-512}" \
  VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  VLLM_XPU_GDN_ISOLATE_QKVZ_PREFILL_REQUESTS=1 \
  VLLM_XPU_GDN_ISOLATE_PREFILL_REQUESTS=1 \
  VLLM_XPU_GDN_ISOLATE_NORM_PREFILL_REQUESTS="${norm_gate}" \
  VLLM_XPU_GDN_ISOLATE_PROJECTION_PREFILL_REQUESTS="${projection_gate}" \
  "${repo_root}/repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-mtp1-server.sh"
