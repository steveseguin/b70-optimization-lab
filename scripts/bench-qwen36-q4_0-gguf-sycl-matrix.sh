#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_0.gguf}"
LLAMA_BENCH="${LLAMA_BENCH:-/home/steve/src/llama.cpp/build-sycl-2026-f16-bmg2/bin/llama-bench}"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-$(dirname "$(dirname "$(dirname "$LLAMA_BENCH")")")}"
OUT_DIR="${OUT_DIR:-/home/steve/bench-results/qwen36-q4_0-gguf}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${OUT:-$OUT_DIR/sycl-$STAMP.jsonl}"
META="${OUT%.jsonl}.meta.txt"

if [[ "${SOURCE_ONEAPI:-1}" == "1" && -f /opt/intel/oneapi/setvars.sh ]]; then
  # shellcheck disable=SC1091
  set +u
  source /opt/intel/oneapi/setvars.sh --force >/dev/null
  set -u
fi

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0}"
export ZES_ENABLE_SYSMAN="${ZES_ENABLE_SYSMAN:-1}"
export UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS="${UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS:-1}"
export GGML_SYCL_ENABLE_GRAPH="${GGML_SYCL_ENABLE_GRAPH:-0}"
export GGML_SYCL_GRAPH_CACHE_SIZE="${GGML_SYCL_GRAPH_CACHE_SIZE:-0}"
export GGML_SYCL_FUSE_MMVQ_ADD="${GGML_SYCL_FUSE_MMVQ_ADD:-0}"
export GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8="${GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8:-0}"
export GGML_SYCL_FUSE_SWIGLU_Q8="${GGML_SYCL_FUSE_SWIGLU_Q8:-0}"
export GGML_SYCL_FUSE_SSM_CONV_SILU="${GGML_SYCL_FUSE_SSM_CONV_SILU:-0}"
export GGML_SYCL_FUSE_GDN_CACHE="${GGML_SYCL_FUSE_GDN_CACHE:-0}"
export GGML_SYCL_CYCLE_TIMING="${GGML_SYCL_CYCLE_TIMING:-0}"

mkdir -p "$OUT_DIR"

{
  echo "date_utc=$STAMP"
  echo "model=$MODEL"
  echo "llama_bench=$LLAMA_BENCH"
  echo "llama_cpp_dir=$LLAMA_CPP_DIR"
  echo "ONEAPI_DEVICE_SELECTOR=$ONEAPI_DEVICE_SELECTOR"
  echo "ZES_ENABLE_SYSMAN=$ZES_ENABLE_SYSMAN"
  echo "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=$UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS"
  echo "GGML_SYCL_ENABLE_GRAPH=$GGML_SYCL_ENABLE_GRAPH"
  echo "GGML_SYCL_GRAPH_CACHE_SIZE=$GGML_SYCL_GRAPH_CACHE_SIZE"
  echo "GGML_SYCL_FUSE_MMVQ_ADD=$GGML_SYCL_FUSE_MMVQ_ADD"
  echo "GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8=$GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8"
  echo "GGML_SYCL_FUSE_SWIGLU_Q8=$GGML_SYCL_FUSE_SWIGLU_Q8"
  echo "GGML_SYCL_FUSE_SSM_CONV_SILU=$GGML_SYCL_FUSE_SSM_CONV_SILU"
  echo "GGML_SYCL_FUSE_GDN_CACHE=$GGML_SYCL_FUSE_GDN_CACHE"
  echo "GGML_SYCL_CYCLE_TIMING=$GGML_SYCL_CYCLE_TIMING"
  echo "sycl_graph_evidence=[SYCL-GRAPH] requested|compatibility_rejected|recording_entered|replayed|summary"
  git -C "$LLAMA_CPP_DIR" rev-parse --short HEAD 2>/dev/null | sed 's/^/llama_cpp_commit=/'
  git -C "$LLAMA_CPP_DIR" diff --stat 2>/dev/null | sed 's/^/llama_cpp_diff_stat=/'
  sycl-ls 2>&1 || true
} > "$META"

COMMON=(
  -m "$MODEL"
  -dev "${DEVICE:-SYCL0}"
  -ngl "${N_GPU_LAYERS:-99}"
  -p "${PROMPT_TOKENS:-0}"
  -n "${OUTPUT_TOKENS:-512}"
  -sm "${SPLIT_MODE:-none}"
  -b "${BATCH_SIZE:-512}"
  -ctk "${CACHE_TYPE_K:-f16}"
  -ctv "${CACHE_TYPE_V:-f16}"
  -t "${THREADS:-8}"
  -r "${REPS:-3}"
  -o jsonl
  --progress
)

if [[ "${NO_WARMUP:-1}" == "1" ]]; then
  COMMON+=(--no-warmup)
fi

if [[ -n "${TENSOR_SPLIT:-}" ]]; then
  COMMON+=(-ts "$TENSOR_SPLIT")
fi

: > "$OUT"

for fa in ${FA_LIST:-1 0}; do
  for ub in ${UB_LIST:-512 256 128 64}; do
    for enable_opt in ${ENABLE_OPT_LIST:-1 0}; do
      for enable_dnn in ${ENABLE_DNN_LIST:-1 0}; do
        export GGML_SYCL_ENABLE_OPT="$enable_opt"
        export GGML_SYCL_ENABLE_DNN="$enable_dnn"
        echo "## fa=$fa ub=$ub GGML_SYCL_ENABLE_GRAPH=$GGML_SYCL_ENABLE_GRAPH GGML_SYCL_ENABLE_OPT=$enable_opt GGML_SYCL_ENABLE_DNN=$enable_dnn" | tee -a "$META" >&2
        "$LLAMA_BENCH" "${COMMON[@]}" -fa "$fa" -ub "$ub" >> "$OUT" \
          2> >(tee -a "$META" >&2)
      done
    done
  done
done

echo "$OUT"
