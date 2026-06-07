#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
profile="${VLLM_SLOT_PROFILE:-/etc/b70-vllm-slot/current.env}"

if [[ ! -f "$profile" ]]; then
  echo "Missing vLLM model-slot profile: $profile" >&2
  exit 1
fi

source "$profile"

export MODEL_SLOT_NAME="${MODEL_SLOT_NAME:-unknown}"
export MODEL_SLOT_TITLE="${MODEL_SLOT_TITLE:-$MODEL_SLOT_NAME}"
export MODEL_SLOT_HF_ID="${MODEL_SLOT_HF_ID:-}"
export MODEL_SLOT_MODALITIES="${MODEL_SLOT_MODALITIES:-}"
export MODEL_SLOT_STATUS="${MODEL_SLOT_STATUS:-}"
export FRONTDOOR_HOST="${FRONTDOOR_HOST:-0.0.0.0}"
export FRONTDOOR_PORT="${FRONTDOOR_PORT:-8000}"
export FRONTDOOR_BACKEND_URL="${FRONTDOOR_BACKEND_URL:-http://127.0.0.1:18080}"
export FRONTDOOR_MAX_ACTIVE_GENERATIONS="${FRONTDOOR_MAX_ACTIVE_GENERATIONS:-1}"
export FRONTDOOR_QUEUE_TIMEOUT_S="${FRONTDOOR_QUEUE_TIMEOUT_S:-3600}"
export FRONTDOOR_BACKEND_TIMEOUT_S="${FRONTDOOR_BACKEND_TIMEOUT_S:-7200}"
export FRONTDOOR_PAUSE_FILE="${FRONTDOOR_PAUSE_FILE:-/home/steve/llm-optimizations/.pause-vllm-model-slot}"
export FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON="${FRONTDOOR_CHAT_TEMPLATE_KWARGS_JSON:-}"

exec "$repo_dir/scripts/openai-lan-frontdoor.py"
