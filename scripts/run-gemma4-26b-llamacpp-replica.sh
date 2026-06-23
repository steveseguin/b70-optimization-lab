#!/usr/bin/env bash
set -euo pipefail

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-18260}"
HOST="${HOST:-127.0.0.1}"
MODEL="${MODEL:-/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf}"
LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-server}"
MODEL_ALIAS="${MODEL_ALIAS:-gemma4-26b-a4b-q8}"
CTX_SIZE="${CTX_SIZE:-32768}"
BATCH_SIZE="${BATCH_SIZE:-512}"
UBATCH_SIZE="${UBATCH_SIZE:-128}"
N_GPU_LAYERS="${N_GPU_LAYERS:-99}"
THREADS="${THREADS:-8}"
FLASH_ATTN="${FLASH_ATTN:-on}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG:-$OUT_DIR/replica-gpu${GPU_INDEX}-port${PORT}-$STAMP.log}"

if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
  # shellcheck disable=SC1091
  set +u
  source /opt/intel/oneapi/setvars.sh --force >/dev/null
  set -u
fi

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:$GPU_INDEX}"
export ZES_ENABLE_SYSMAN="${ZES_ENABLE_SYSMAN:-1}"
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS="${UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS:-1}"
export GGML_SYCL_DISABLE_OPT="${GGML_SYCL_DISABLE_OPT:-1}"

mkdir -p "$OUT_DIR"

{
  echo "date_utc=$STAMP"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "model=$MODEL"
  echo "llama_server=$LLAMA_SERVER"
  echo "ONEAPI_DEVICE_SELECTOR=$ONEAPI_DEVICE_SELECTOR"
  echo "GGML_SYCL_DISABLE_OPT=$GGML_SYCL_DISABLE_OPT"
  echo "GGML_SYCL_DISABLE_GRAPH=${GGML_SYCL_DISABLE_GRAPH:-<unset>}"
  echo "GGML_SYCL_DISABLE_DNN=${GGML_SYCL_DISABLE_DNN:-<unset>}"
  "$LLAMA_SERVER" --version 2>&1 || true
  sycl-ls 2>&1 || true
  echo "--- server ---"
} > "$LOG"

exec "$LLAMA_SERVER" \
  -m "$MODEL" \
  --alias "$MODEL_ALIAS" \
  --host "$HOST" \
  --port "$PORT" \
  -dev SYCL0 \
  -ngl "$N_GPU_LAYERS" \
  -c "$CTX_SIZE" \
  -b "$BATCH_SIZE" \
  -ub "$UBATCH_SIZE" \
  -t "$THREADS" \
  -ctk "$CACHE_TYPE_K" \
  -ctv "$CACHE_TYPE_V" \
  -fa "$FLASH_ATTN" \
  --jinja \
  2>&1 | tee -a "$LOG"
