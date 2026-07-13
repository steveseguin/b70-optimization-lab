#!/usr/bin/env bash
set -euo pipefail

GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19430}"
HOST="${HOST:-127.0.0.1}"
MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_0.gguf}"
MODEL_ALIAS="${MODEL_ALIAS:-qwen36-27b-mtp-gguf-q4_0}"
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
SPEC_PROFILE="${SPEC_PROFILE:-custom}"
case "$SPEC_PROFILE" in
  custom)
    if [[ -z "${SPEC_TYPE:-}" ]]; then
      if [[ "$ENABLE_MTP" == "1" ]]; then
        SPEC_TYPE="draft-mtp"
      else
        SPEC_TYPE="none"
      fi
    fi
    ;;
  no-spec)
    SPEC_TYPE="none"
    ;;
  mtp3)
    SPEC_TYPE="draft-mtp"
    SPEC_N_MAX=3
    ;;
  dflash5|dflash8|dflash15)
    SPEC_TYPE="draft-simple"
    SPEC_N_MAX="${SPEC_PROFILE#dflash}"
    ;;
  native-dflash2|native-dflash3|native-dflash4|native-dflash5|native-dflash8|native-dflash15)
    SPEC_TYPE="draft-dflash"
    SPEC_N_MAX="${SPEC_PROFILE#native-dflash}"
    DRAFT_MODEL="${DRAFT_MODEL:-/mnt/usb-models/models/qwen36-27b-dflash-native/Qwen3.6-27B-DFlash-Q8_0.gguf}"
    # Native DFlash requires F16 draft KV for acceptance correctness on SYCL.
    # Flash attention itself is valid when the draft KV remains F16.
    FLASH_ATTN=on
    DRAFT_CACHE_TYPE_K="${DRAFT_CACHE_TYPE_K:-f16}"
    DRAFT_CACHE_TYPE_V="${DRAFT_CACHE_TYPE_V:-f16}"
    ;;
  *)
    echo "Invalid SPEC_PROFILE=$SPEC_PROFILE; expected custom, no-spec, mtp3, dflash5, dflash8, dflash15, or native-dflash{2,3,4,5,8,15}" >&2
    exit 2
    ;;
esac
SPEC_N_MAX="${SPEC_N_MAX:-$MTP_N_MAX}"
SPEC_N_MIN="${SPEC_N_MIN:-$MTP_N_MIN}"
SPEC_P_MIN="${SPEC_P_MIN:-$MTP_P_MIN}"
DRAFT_MODEL="${DRAFT_MODEL:-}"
DRAFT_DEVICE="${DRAFT_DEVICE:-SYCL0}"
DRAFT_NGL="${DRAFT_NGL:-all}"
DRAFT_CACHE_TYPE_K="${DRAFT_CACHE_TYPE_K:-q8_0}"
DRAFT_CACHE_TYPE_V="${DRAFT_CACHE_TYPE_V:-q8_0}"
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
export GGML_SYCL_ENABLE_GRAPH="${GGML_SYCL_ENABLE_GRAPH:-0}"
export GGML_SYCL_GRAPH_CACHE_SIZE="${GGML_SYCL_GRAPH_CACHE_SIZE:-0}"
export GGML_SYCL_FUSE_MMVQ_ADD="${GGML_SYCL_FUSE_MMVQ_ADD:-0}"
export GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8="${GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8:-0}"
export GGML_SYCL_FUSE_SWIGLU_Q8="${GGML_SYCL_FUSE_SWIGLU_Q8:-0}"
export GGML_SYCL_FUSE_SSM_CONV_SILU="${GGML_SYCL_FUSE_SSM_CONV_SILU:-0}"
export GGML_SYCL_FUSE_SSM_CONV_CACHE="${GGML_SYCL_FUSE_SSM_CONV_CACHE:-0}"
export GGML_SYCL_FUSE_SSM_CONV_QK_NORM="${GGML_SYCL_FUSE_SSM_CONV_QK_NORM:-0}"
export GGML_SYCL_FUSE_GDN_CACHE="${GGML_SYCL_FUSE_GDN_CACHE:-0}"
export GGML_SYCL_FUSE_GDN_RAW_GATES="${GGML_SYCL_FUSE_GDN_RAW_GATES:-0}"
export GGML_SYCL_FUSE_GDN_EPILOGUE="${GGML_SYCL_FUSE_GDN_EPILOGUE:-0}"
export GGML_SYCL_CYCLE_TIMING="${GGML_SYCL_CYCLE_TIMING:-0}"
export LLAMA_MTP_DEVICE_UNROLL="${LLAMA_MTP_DEVICE_UNROLL:-0}"
export LLAMA_DFLASH_CYCLE_TIMING="${LLAMA_DFLASH_CYCLE_TIMING:-0}"
export LLAMA_DFLASH_FUSED_TOP1="${LLAMA_DFLASH_FUSED_TOP1:-0}"
export LLAMA_DFLASH_TOP1_FORCE_READ_FAIL="${LLAMA_DFLASH_TOP1_FORCE_READ_FAIL:-0}"
export GGML_SYCL_ENABLE_DNN="${GGML_SYCL_ENABLE_DNN:-1}"
export GGML_SYCL_ENABLE_OPT="${GGML_SYCL_ENABLE_OPT:-1}"
export GGML_SYCL_ENABLE_VMM="${GGML_SYCL_ENABLE_VMM:-1}"
export GGML_SYCL_XE2_Q4_M6_FFN="${GGML_SYCL_XE2_Q4_M6_FFN:-0}"
export GGML_SYCL_XE2_Q4_M6_PACK_LIMIT="${GGML_SYCL_XE2_Q4_M6_PACK_LIMIT:-0}"
export GGML_SYCL_XE2_Q4_M6_PACK_CACHE="${GGML_SYCL_XE2_Q4_M6_PACK_CACHE:-}"
export GGML_SYCL_XE2_Q4_M6_COMPARE="${GGML_SYCL_XE2_Q4_M6_COMPARE:-0}"
export GGML_SYCL_XE2_Q4_M6_GATE_UP="${GGML_SYCL_XE2_Q4_M6_GATE_UP:-0}"
export GGML_SYCL_XE2_Q6_M6_TOP1="${GGML_SYCL_XE2_Q6_M6_TOP1:-0}"

extra_args=()
if [[ -n "$EXTRA_LLAMA_ARGS" ]]; then
  read -r -a extra_args <<< "$EXTRA_LLAMA_ARGS"
fi

spec_args=()
case "$SPEC_TYPE" in
  none)
    ;;
  draft-mtp)
    spec_args=(
      --spec-type draft-mtp
      --spec-draft-n-max "$SPEC_N_MAX"
      --spec-draft-n-min "$SPEC_N_MIN"
      --spec-draft-p-min "$SPEC_P_MIN"
    )
    if [[ -n "$DRAFT_MODEL" ]]; then
      spec_args+=(
        --spec-draft-model "$DRAFT_MODEL"
        --spec-draft-device "$DRAFT_DEVICE"
        --spec-draft-ngl "$DRAFT_NGL"
        --spec-draft-type-k "$DRAFT_CACHE_TYPE_K"
        --spec-draft-type-v "$DRAFT_CACHE_TYPE_V"
      )
    fi
    ;;
  draft-simple|draft-dflash)
    DRAFT_MODEL="${DRAFT_MODEL:-/mnt/usb-models/models/qwen36-27b-dflash-gguf/Qwen3.6-27B-DFlash-Q4_K_M.gguf}"
    spec_args=(
      --spec-type "$SPEC_TYPE"
      --spec-draft-model "$DRAFT_MODEL"
      --spec-draft-device "$DRAFT_DEVICE"
      --spec-draft-ngl "$DRAFT_NGL"
      --spec-draft-type-k "$DRAFT_CACHE_TYPE_K"
      --spec-draft-type-v "$DRAFT_CACHE_TYPE_V"
      --spec-draft-n-max "$SPEC_N_MAX"
      --spec-draft-n-min "$SPEC_N_MIN"
      --spec-draft-p-min "$SPEC_P_MIN"
    )
    ;;
  *)
    echo "Invalid SPEC_TYPE=$SPEC_TYPE; expected none, draft-mtp, draft-simple, or draft-dflash" >&2
    exit 2
    ;;
esac

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
  echo "spec_profile=$SPEC_PROFILE"
  echo "spec_type=$SPEC_TYPE"
  echo "spec_n_max=$SPEC_N_MAX"
  echo "spec_n_min=$SPEC_N_MIN"
  echo "spec_p_min=$SPEC_P_MIN"
  echo "draft_model=${DRAFT_MODEL:-<embedded-or-none>}"
  echo "draft_device=$DRAFT_DEVICE"
  echo "draft_ngl=$DRAFT_NGL"
  echo "draft_cache_type_k=$DRAFT_CACHE_TYPE_K"
  echo "draft_cache_type_v=$DRAFT_CACHE_TYPE_V"
  echo "extra_llama_args=$EXTRA_LLAMA_ARGS"
  echo "ONEAPI_DEVICE_SELECTOR=$ONEAPI_DEVICE_SELECTOR"
  echo "ZE_AFFINITY_MASK=$ZE_AFFINITY_MASK"
  echo "GGML_SYCL_ENABLE_GRAPH=$GGML_SYCL_ENABLE_GRAPH"
  echo "GGML_SYCL_GRAPH_CACHE_SIZE=$GGML_SYCL_GRAPH_CACHE_SIZE"
  echo "GGML_SYCL_FUSE_MMVQ_ADD=$GGML_SYCL_FUSE_MMVQ_ADD"
  echo "GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8=$GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8"
  echo "GGML_SYCL_FUSE_SWIGLU_Q8=$GGML_SYCL_FUSE_SWIGLU_Q8"
  echo "GGML_SYCL_FUSE_SSM_CONV_SILU=$GGML_SYCL_FUSE_SSM_CONV_SILU"
  echo "GGML_SYCL_FUSE_SSM_CONV_CACHE=$GGML_SYCL_FUSE_SSM_CONV_CACHE"
  echo "GGML_SYCL_FUSE_SSM_CONV_QK_NORM=$GGML_SYCL_FUSE_SSM_CONV_QK_NORM"
  echo "GGML_SYCL_FUSE_GDN_CACHE=$GGML_SYCL_FUSE_GDN_CACHE"
  echo "GGML_SYCL_FUSE_GDN_RAW_GATES=$GGML_SYCL_FUSE_GDN_RAW_GATES"
  echo "GGML_SYCL_FUSE_GDN_EPILOGUE=$GGML_SYCL_FUSE_GDN_EPILOGUE"
  echo "GGML_SYCL_CYCLE_TIMING=$GGML_SYCL_CYCLE_TIMING"
  echo "LLAMA_MTP_DEVICE_UNROLL=$LLAMA_MTP_DEVICE_UNROLL"
  echo "LLAMA_DFLASH_CYCLE_TIMING=$LLAMA_DFLASH_CYCLE_TIMING"
  echo "LLAMA_DFLASH_FUSED_TOP1=$LLAMA_DFLASH_FUSED_TOP1"
  echo "LLAMA_DFLASH_TOP1_FORCE_READ_FAIL=$LLAMA_DFLASH_TOP1_FORCE_READ_FAIL"
  echo "GGML_SYCL_ENABLE_DNN=$GGML_SYCL_ENABLE_DNN"
  echo "GGML_SYCL_ENABLE_OPT=$GGML_SYCL_ENABLE_OPT"
  echo "GGML_SYCL_ENABLE_VMM=$GGML_SYCL_ENABLE_VMM"
  echo "GGML_SYCL_XE2_Q4_M6_FFN=$GGML_SYCL_XE2_Q4_M6_FFN"
  echo "GGML_SYCL_XE2_Q4_M6_PACK_LIMIT=$GGML_SYCL_XE2_Q4_M6_PACK_LIMIT"
  echo "GGML_SYCL_XE2_Q4_M6_PACK_CACHE=${GGML_SYCL_XE2_Q4_M6_PACK_CACHE:-disabled}"
  echo "GGML_SYCL_XE2_Q4_M6_COMPARE=$GGML_SYCL_XE2_Q4_M6_COMPARE"
  echo "GGML_SYCL_XE2_Q4_M6_GATE_UP=$GGML_SYCL_XE2_Q4_M6_GATE_UP"
  echo "GGML_SYCL_XE2_Q6_M6_TOP1=$GGML_SYCL_XE2_Q6_M6_TOP1"
  echo "sycl_graph_evidence=[SYCL-GRAPH] requested|compatibility_rejected|recording_entered|replayed|summary"
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
