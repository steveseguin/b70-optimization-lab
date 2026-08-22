#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

LLAMA_SERVER="${LLAMA_SERVER:-}"
MODEL="${MODEL:-}"
MTP_DRAFT_MODEL="${MTP_DRAFT_MODEL:-}"
DRAFT_SHA256="${DRAFT_SHA256:-}"
[[ -x "$LLAMA_SERVER" ]] || { echo "Set LLAMA_SERVER to the reconstructed binary." >&2; exit 2; }
[[ -f "$MODEL" ]] || { echo "Set MODEL to the pinned UD-Q8_K_XL GGUF." >&2; exit 2; }
[[ -f "$MTP_DRAFT_MODEL" ]] || { echo "Set MTP_DRAFT_MODEL to the local Q4_0 MTP GGUF." >&2; exit 2; }
LLAMA_SERVER="$LLAMA_SERVER" MODEL="$MODEL" MTP_DRAFT_MODEL="$MTP_DRAFT_MODEL" \
  DRAFT_SHA256="$DRAFT_SHA256" \
  repro/gemma4-26b-a4b-q8-b70-125tps-20260701/preflight.sh

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19350}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${LABEL:-gemma4-q8-gpu${GPU_INDEX}-125repro-${STAMP}}"

GPU_INDEX="$GPU_INDEX" \
PORT="$PORT" \
LABEL="$LABEL" \
LLAMA_SERVER="$LLAMA_SERVER" \
MODEL="$MODEL" \
EXTRA_LLAMA_ARGS="--parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model $MTP_DRAFT_MODEL --spec-draft-n-max 3 --spec-draft-device SYCL0 --spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16 --spec-draft-n-min 2 --spec-draft-p-min 0.0475 --no-spec-draft-backend-sampling --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0" \
CTX_SIZE="${CTX_SIZE:-32768}" \
FLASH_ATTN="${FLASH_ATTN:-on}" \
GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}" \
CANARY_REPEATS="${CANARY_REPEATS:-128}" \
MAX_TOKENS="${MAX_TOKENS:-512}" \
REALISTIC_GATE="${REALISTIC_GATE:-1}" \
REALISTIC_METRIC_TOKENS="${REALISTIC_METRIC_TOKENS:-100}" \
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}" \
bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
