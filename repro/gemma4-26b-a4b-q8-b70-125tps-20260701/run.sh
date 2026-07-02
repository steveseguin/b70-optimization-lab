#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19350}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-gemma4-q8-gpu${GPU_INDEX}-125repro-${STAMP}}"

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
LABEL="$LABEL" \
CTX_SIZE="${CTX_SIZE:-32768}" \
FLASH_ATTN="${FLASH_ATTN:-on}" \
GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}" \
CANARY_REPEATS="${CANARY_REPEATS:-128}" \
MAX_TOKENS="${MAX_TOKENS:-512}" \
REALISTIC_GATE="${REALISTIC_GATE:-1}" \
REALISTIC_METRIC_TOKENS="${REALISTIC_METRIC_TOKENS:-100}" \
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}" \
bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
