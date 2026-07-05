#!/usr/bin/env bash
set -euo pipefail

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19430}"
HOST="${HOST:-127.0.0.1}"
MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-UD-Q4_K_XL.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen36-27b-mtp-gguf-q4}"
LLAMA_SERVER="${LLAMA_SERVER:-/home/steve/src/llama.cpp/build-sycl-b70-qwen36-mtp/bin/llama-server}"
CTX_SIZE="${CTX_SIZE:-4096}"
BATCH_SIZE="${BATCH_SIZE:-1024}"
UBATCH_SIZE="${UBATCH_SIZE:-256}"
N_GPU_LAYERS="${N_GPU_LAYERS:-99}"
THREADS="${THREADS:-8}"
N_PARALLEL="${N_PARALLEL:-1}"
POLL="${POLL:-50}"
FLASH_ATTN="${FLASH_ATTN:-on}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
REASONING="${REASONING:-off}"
LLAMA_DEVICES="${LLAMA_DEVICES:-SYCL0}"
ENABLE_MTP="${ENABLE_MTP:-1}"
MTP_N_MAX="${MTP_N_MAX:-3}"
MTP_N_MIN="${MTP_N_MIN:-0}"
MTP_P_MIN="${MTP_P_MIN:-0.00}"
EXTRA_LLAMA_ARGS="${EXTRA_LLAMA_ARGS:---cache-ram 0}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG:-$OUT_DIR/llamacpp-gpu${GPU_INDEX}-port${PORT}-$STAMP.log}"

if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
  # shellcheck disable=SC1091
  set +u
  source /opt/intel/oneapi/setvars.sh --force >/dev/null
  set -u
fi

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:*}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-$GPU_INDEX}"
export ZES_ENABLE_SYSMAN="${ZES_ENABLE_SYSMAN:-1}"
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS="${UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS:-1}"
export GGML_SYCL_DISABLE_GRAPH="${GGML_SYCL_DISABLE_GRAPH:-0}"
export GGML_SYCL_DISABLE_DNN="${GGML_SYCL_DISABLE_DNN:-0}"
export GGML_SYCL_DISABLE_OPT="${GGML_SYCL_DISABLE_OPT:-0}"
export GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}"

extra_args=()
if [[ -n "$EXTRA_LLAMA_ARGS" ]]; then
  read -r -a extra_args <<< "$EXTRA_LLAMA_ARGS"
fi

spec_args=()
if [[ "$ENABLE_MTP" == "1" ]]; then
  spec_args=(
    --spec-type draft-mtp
    --spec-draft-n-max "$MTP_N_MAX"
    --spec-draft-n-min "$MTP_N_MIN"
    --spec-draft-p-min "$MTP_P_MIN"
  )
fi

mkdir -p "$OUT_DIR"

{
  echo "date_utc=$STAMP"
  echo "gpu_index=$GPU_INDEX"
  echo "host=$HOST"
  echo "port=$PORT"
  echo "model=$MODEL"
  echo "model_alias=$MODEL_ALIAS"
  echo "llama_server=$LLAMA_SERVER"
  echo "llama_cpp_commit=$(git -C "$(dirname "$LLAMA_SERVER")/../.." rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "ctx_size=$CTX_SIZE"
  echo "batch_size=$BATCH_SIZE"
  echo "ubatch_size=$UBATCH_SIZE"
  echo "n_gpu_layers=$N_GPU_LAYERS"
  echo "threads=$THREADS"
  echo "n_parallel=$N_PARALLEL"
  echo "poll=$POLL"
  echo "flash_attn=$FLASH_ATTN"
  echo "cache_type_k=$CACHE_TYPE_K"
  echo "cache_type_v=$CACHE_TYPE_V"
  echo "reasoning=$REASONING"
  echo "llama_devices=$LLAMA_DEVICES"
  echo "enable_mtp=$ENABLE_MTP"
  echo "mtp_n_max=$MTP_N_MAX"
  echo "mtp_n_min=$MTP_N_MIN"
  echo "mtp_p_min=$MTP_P_MIN"
  echo "extra_llama_args=$EXTRA_LLAMA_ARGS"
  echo "ONEAPI_DEVICE_SELECTOR=$ONEAPI_DEVICE_SELECTOR"
  echo "ZE_AFFINITY_MASK=$ZE_AFFINITY_MASK"
  echo "GGML_SYCL_DISABLE_GRAPH=$GGML_SYCL_DISABLE_GRAPH"
  echo "GGML_SYCL_DISABLE_DNN=$GGML_SYCL_DISABLE_DNN"
  echo "GGML_SYCL_DISABLE_OPT=$GGML_SYCL_DISABLE_OPT"
  echo "GGML_SYCL_ENABLE_VMM=$GGML_SYCL_ENABLE_VMM"
  "$LLAMA_SERVER" --version 2>&1 || true
  sycl-ls 2>&1 || true
  echo "--- server ---"
} > "$LOG"

exec > >(tee -a "$LOG") 2>&1
exec "$LLAMA_SERVER" \
  -m "$MODEL" \
  --alias "$MODEL_ALIAS" \
  --host "$HOST" \
  --port "$PORT" \
  -dev "$LLAMA_DEVICES" \
  -ngl "$N_GPU_LAYERS" \
  -c "$CTX_SIZE" \
  -np "$N_PARALLEL" \
  -b "$BATCH_SIZE" \
  -ub "$UBATCH_SIZE" \
  -t "$THREADS" \
  --poll "$POLL" \
  -ctk "$CACHE_TYPE_K" \
  -ctv "$CACHE_TYPE_V" \
  -fa "$FLASH_ATTN" \
  --reasoning "$REASONING" \
  --ctx-checkpoints 0 \
  --jinja \
  "${spec_args[@]}" \
  "${extra_args[@]}"
