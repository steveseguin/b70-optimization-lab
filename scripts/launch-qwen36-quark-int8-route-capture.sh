#!/usr/bin/env bash
set -euo pipefail

# Diagnostic wrapper around the accepted Qwen3.6 Quark W8A8 INT8 launcher.
# It enables bounded MoE router histogram capture and uses an isolated graph
# cache so the production/accepted cache remains untouched.

TAG="${TAG:-routecapture}"
if [[ -z "${CAPTURE_FILE:-}" ]]; then
  CAPTURE_FILE="/tmp/qwen36-moe-routes-${TAG}"'-{pid}.jsonl'
fi
CAPTURE_MAX_LINES="${CAPTURE_MAX_LINES:-0}"
CAPTURE_EVERY_N="${CAPTURE_EVERY_N:-1}"
CAPTURE_INCLUDE_IDS="${CAPTURE_INCLUDE_IDS:-0}"
CAPTURE_LAYER_REGEX="${CAPTURE_LAYER_REGEX:-}"
CAPTURE_STAGE_REGEX="${CAPTURE_STAGE_REGEX:-}"
CAPTURE_MIN_NUM_TOKENS="${CAPTURE_MIN_NUM_TOKENS:-0}"
CAPTURE_MAX_NUM_TOKENS="${CAPTURE_MAX_NUM_TOKENS:-0}"

export VLLM_MOE_ROUTE_CAPTURE_FILE="$CAPTURE_FILE"
export VLLM_MOE_ROUTE_CAPTURE_MAX_LINES="$CAPTURE_MAX_LINES"
export VLLM_MOE_ROUTE_CAPTURE_EVERY_N="$CAPTURE_EVERY_N"
export VLLM_MOE_ROUTE_CAPTURE_INCLUDE_IDS="$CAPTURE_INCLUDE_IDS"
export VLLM_MOE_ROUTE_CAPTURE_LAYER_REGEX="$CAPTURE_LAYER_REGEX"
export VLLM_MOE_ROUTE_CAPTURE_STAGE_REGEX="$CAPTURE_STAGE_REGEX"
export VLLM_MOE_ROUTE_CAPTURE_MIN_NUM_TOKENS="$CAPTURE_MIN_NUM_TOKENS"
export VLLM_MOE_ROUTE_CAPTURE_MAX_NUM_TOKENS="$CAPTURE_MAX_NUM_TOKENS"

export XPU_GRAPH="${XPU_GRAPH:-0}"
export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-0}"
export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-0}"
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-0}"
export VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:---enforce-eager}"

export LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${TAG}-route-capture.log}"
DEFAULT_CACHE_ROOT="/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-${TAG}-route-capture"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-${DEFAULT_CACHE_ROOT}/torchinductor}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-${DEFAULT_CACHE_ROOT}/vllm}"

exec /home/steve/llm-optimizations/scripts/launch-qwen36-quark-int8-accepted.sh
