#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MANIFEST="$ROOT/experiments/qwen36-27b-q8-gguf-b70/model-manifest.json"
RUNTIME_MANIFEST="${RUNTIME_MANIFEST:-$ROOT/experiments/qwen36-27b-q8-gguf-b70/runtime-manifest.json}"

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19460}"
HOST="${HOST:-127.0.0.1}"
MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen36-27b-q8_0-target-only}"
LLAMA_SERVER="${LLAMA_SERVER:-/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server}"
CTX_SIZE="${CTX_SIZE:-32768}"
BATCH_SIZE="${BATCH_SIZE:-1024}"
UBATCH_SIZE="${UBATCH_SIZE:-128}"
N_GPU_LAYERS="${N_GPU_LAYERS:-99}"
THREADS="${THREADS:-8}"
POLL="${POLL:-50}"
LOG_VERBOSITY="${LOG_VERBOSITY:-4}"
LANE_DNN_ENABLED="${LANE_DNN_ENABLED:-0}"
LANE_OPT_ENABLED="${LANE_OPT_ENABLED:-1}"
FLASH_ATTN="${FLASH_ATTN:-on}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
OUT_DIR="${OUT_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/servers}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG:-$OUT_DIR/target-only-gpu${GPU_INDEX}-port${PORT}-${STAMP}.log}"

if [[ ! "$GPU_INDEX" =~ ^[0-3]$ ]]; then
  echo "GPU_INDEX must be 0, 1, 2, or 3" >&2
  exit 2
fi
if [[ "$HOST" != "127.0.0.1" ]]; then
  echo "validation launcher requires HOST=127.0.0.1" >&2
  exit 2
fi
if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1024 || PORT > 65535 )); then
  echo "PORT must be an integer from 1024 through 65535" >&2
  exit 2
fi
if [[ ! "$LOG_VERBOSITY" =~ ^[3-5]$ ]]; then
  echo "LOG_VERBOSITY must be 3, 4, or 5" >&2
  exit 2
fi
for toggle_name in LANE_DNN_ENABLED LANE_OPT_ENABLED; do
  toggle_value="${!toggle_name}"
  if [[ "$toggle_value" != "0" && "$toggle_value" != "1" ]]; then
    echo "$toggle_name must be 0 or 1" >&2
    exit 2
  fi
done

unexpected_env=()
while IFS='=' read -r name _; do
  case "$name" in
    GGML_*|SYCL_*|ZE_*|ZES_*|UR_*|ONEAPI_DEVICE_SELECTOR|LD_PRELOAD)
      unexpected_env+=("$name")
      ;;
    LLAMA_*)
      [[ "$name" == "LLAMA_SERVER" ]] || unexpected_env+=("$name")
      ;;
  esac
done < <(env)
if (( ${#unexpected_env[@]} > 0 )); then
  printf 'unexpected inherited runtime environment: %s\n' "${unexpected_env[*]}" >&2
  exit 2
fi

EXPECTED_SIZE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["size_bytes"])' "$MANIFEST")"
EXPECTED_RUNTIME_SHA256="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["llama_server_sha256"])' "$RUNTIME_MANIFEST")"
EXPECTED_RUNTIME_VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["runtime_version_line"])' "$RUNTIME_MANIFEST")"
if [[ ! -f "$MODEL" ]]; then
  echo "model not found: $MODEL" >&2
  exit 2
fi
ACTUAL_SIZE="$(stat -c %s "$MODEL")"
if [[ "$ACTUAL_SIZE" != "$EXPECTED_SIZE" ]]; then
  echo "model size mismatch: expected $EXPECTED_SIZE, got $ACTUAL_SIZE" >&2
  exit 2
fi
if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "llama-server not executable: $LLAMA_SERVER" >&2
  exit 2
fi
ACTUAL_RUNTIME_SHA256="$(sha256sum "$LLAMA_SERVER" | awk '{print $1}')"
if [[ "$ACTUAL_RUNTIME_SHA256" != "$EXPECTED_RUNTIME_SHA256" ]]; then
  echo "llama-server SHA-256 mismatch" >&2
  exit 2
fi
if ss -H -ltn "sport = :$PORT" | grep -q .; then
  echo "port already in use: $PORT" >&2
  exit 2
fi

if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
  set +u
  # shellcheck disable=SC1091
  source /opt/intel/oneapi/setvars.sh --force >/dev/null
  set -u
fi

export ONEAPI_DEVICE_SELECTOR="level_zero:*"
export ZE_AFFINITY_MASK="$GPU_INDEX"
export ZES_ENABLE_SYSMAN=1
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
export GGML_SYCL_ENABLE_VMM=1
export GGML_SYCL_ENABLE_GRAPH=0
export GGML_SYCL_GRAPH_CACHE_SIZE=0
export GGML_SYCL_ENABLE_DNN="$LANE_DNN_ENABLED"
export GGML_SYCL_ENABLE_OPT="$LANE_OPT_ENABLED"

RUNTIME_VERSION="$($LLAMA_SERVER --version 2>&1)"
if ! grep -Fqx "$EXPECTED_RUNTIME_VERSION" <<< "$RUNTIME_VERSION"; then
  echo "llama-server version mismatch" >&2
  exit 2
fi

mkdir -p "$OUT_DIR"
server_cmd=(
  "$LLAMA_SERVER"
  -m "$MODEL"
  --alias "$MODEL_ALIAS"
  --host "$HOST"
  --port "$PORT"
  -dev SYCL0
  -ngl "$N_GPU_LAYERS"
  -c "$CTX_SIZE"
  -np 1
  -b "$BATCH_SIZE"
  -ub "$UBATCH_SIZE"
  -t "$THREADS"
  --poll "$POLL"
  -lv "$LOG_VERBOSITY"
  -ctk "$CACHE_TYPE_K"
  -ctv "$CACHE_TYPE_V"
  -fa "$FLASH_ATTN"
  --spec-type none
  --reasoning off
  --ctx-checkpoints 0
  --cache-ram 0
  --jinja
)
{
  echo "date_utc=$STAMP"
  echo "gpu_index=$GPU_INDEX"
  echo "host=$HOST"
  echo "port=$PORT"
  echo "model=$MODEL"
  echo "model_bytes=$ACTUAL_SIZE"
  echo "model_alias=$MODEL_ALIAS"
  echo "model_manifest=$MANIFEST"
  echo "llama_server=$LLAMA_SERVER"
  echo "llama_server_sha256=$ACTUAL_RUNTIME_SHA256"
  echo "runtime_manifest=$RUNTIME_MANIFEST"
  printf '%s\n' "$RUNTIME_VERSION"
  echo "ctx_size=$CTX_SIZE"
  echo "batch_size=$BATCH_SIZE"
  echo "ubatch_size=$UBATCH_SIZE"
  echo "n_gpu_layers=$N_GPU_LAYERS"
  echo "log_verbosity=$LOG_VERBOSITY"
  echo "flash_attn=$FLASH_ATTN"
  echo "cache_type_k=$CACHE_TYPE_K"
  echo "cache_type_v=$CACHE_TYPE_V"
  echo "speculation=none"
  echo "vision_projector=none"
  echo "reasoning=off"
  echo "ONEAPI_DEVICE_SELECTOR=$ONEAPI_DEVICE_SELECTOR"
  echo "ZE_AFFINITY_MASK=$ZE_AFFINITY_MASK"
  echo "GGML_SYCL_ENABLE_VMM=$GGML_SYCL_ENABLE_VMM"
  echo "GGML_SYCL_ENABLE_GRAPH=$GGML_SYCL_ENABLE_GRAPH"
  echo "GGML_SYCL_ENABLE_DNN=$GGML_SYCL_ENABLE_DNN"
  echo "GGML_SYCL_ENABLE_OPT=$GGML_SYCL_ENABLE_OPT"
  printf 'argv='
  printf '%q ' "${server_cmd[@]}"
  printf '\n'
  echo "--- server ---"
} > "$LOG"

exec > >(tee -a "$LOG") 2>&1
exec "${server_cmd[@]}"
