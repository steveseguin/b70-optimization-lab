#!/usr/bin/env bash
set -euo pipefail

HYBRID_MODEL_PATH="${HYBRID_MODEL_PATH:-/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid}"
SPEC_CONFIG="${SPEC_CONFIG:-{\"method\":\"mtp\",\"num_speculative_tokens\":1,\"max_model_len\":32768}}"

export MODEL_PATH="${MODEL_PATH:-$HYBRID_MODEL_PATH}"
export LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-hybrid-mtp-20260611.log}"
export VLLM_QWEN35_MTP_FORCE_FP8_BLOCK="${VLLM_QWEN35_MTP_FORCE_FP8_BLOCK:-1}"
export VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:---speculative-config $SPEC_CONFIG}"

exec "$(dirname "${BASH_SOURCE[0]}")/launch-qwen36-quark-int8-accepted.sh"
