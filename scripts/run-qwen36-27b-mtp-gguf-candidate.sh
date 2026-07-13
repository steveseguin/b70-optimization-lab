#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GPU_INDEX="${GPU_INDEX:-1}"
PORT="${PORT:-19431}"
SPEC_PROFILE="${SPEC_PROFILE:-mtp3}"
LABEL="${LABEL:-llamacpp-${SPEC_PROFILE}-aot-np1-realistic128}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen36-27b-mtp-gguf-q4-b70-baselines}"
OUT="${OUT:-$OUT_DIR/${LABEL}-${STAMP}.json}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-240}"

# Resolve profile-owned defaults here as well as in the server launcher so the
# pre-run identity describes what will actually execute. The paired source
# Native DFlash keeps flash attention enabled, but requires F16 draft KV until
# the catastrophic Q8_0 draft-cache acceptance failure is understood and fixed.
case "$SPEC_PROFILE" in
  native-dflash2|native-dflash3|native-dflash4|native-dflash5|native-dflash8|native-dflash15)
    SPEC_TYPE="draft-dflash"
    SPEC_N_MAX="${SPEC_PROFILE#native-dflash}"
    DRAFT_MODEL="${DRAFT_MODEL:-/mnt/usb-models/models/qwen36-27b-dflash-native/Qwen3.6-27B-DFlash-Q8_0.gguf}"
    FLASH_ATTN=on
    DRAFT_CACHE_TYPE_K="${DRAFT_CACHE_TYPE_K:-f16}"
    DRAFT_CACHE_TYPE_V="${DRAFT_CACHE_TYPE_V:-f16}"
    ;;
esac

TARGET_MODEL="${MODEL:-/mnt/usb-models/models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_0.gguf}"
API_MODEL="${API_MODEL:-${MODEL_ALIAS:-qwen36-27b-mtp-gguf-q4_0}}"

mkdir -p "$RUN_DIR" "$OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cd "$ROOT"

{
  echo "date_utc=$STAMP"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "label=$LABEL"
  echo "run_dir=$RUN_DIR"
  echo "out=$OUT"
  echo "enable_mtp=${ENABLE_MTP:-1}"
  echo "spec_profile=$SPEC_PROFILE"
  echo "spec_type=${SPEC_TYPE:-<resolved-by-profile>}"
  echo "spec_n_max=${SPEC_N_MAX:-<resolved-by-profile>}"
  echo "spec_n_min=${SPEC_N_MIN:-${MTP_N_MIN:-0}}"
  echo "spec_p_min=${SPEC_P_MIN:-${MTP_P_MIN:-0.00}}"
  echo "draft_model=${DRAFT_MODEL:-<resolved-by-profile>}"
  if [[ -n "${DRAFT_MODEL:-}" && -f "$DRAFT_MODEL" ]]; then
    echo "draft_model_bytes=$(stat -c %s "$DRAFT_MODEL")"
    echo "draft_model_mtime=$(stat -c %Y "$DRAFT_MODEL")"
  fi
  echo "draft_device=${DRAFT_DEVICE:-SYCL0}"
  echo "draft_n_gpu_layers=${DRAFT_NGL:-all}"
  echo "draft_cache_type_k=${DRAFT_CACHE_TYPE_K:-q8_0}"
  echo "draft_cache_type_v=${DRAFT_CACHE_TYPE_V:-q8_0}"
  echo "mtp_n_max=${MTP_N_MAX:-3}"
  echo "mtp_n_min=${MTP_N_MIN:-0}"
  echo "mtp_p_min=${MTP_P_MIN:-0.00}"
  echo "ctx_size=${CTX_SIZE:-4096}"
  echo "batch_size=${BATCH_SIZE:-1024}"
  echo "ubatch_size=${UBATCH_SIZE:-256}"
  echo "n_parallel=${N_PARALLEL:-1}"
  echo "flash_attn=${FLASH_ATTN:-on}"
  echo "cache_type_k=${CACHE_TYPE_K:-q8_0}"
  echo "cache_type_v=${CACHE_TYPE_V:-q8_0}"
  echo "GGML_SYCL_ENABLE_GRAPH=${GGML_SYCL_ENABLE_GRAPH:-1}"
  echo "GGML_SYCL_GRAPH_CACHE_SIZE=${GGML_SYCL_GRAPH_CACHE_SIZE:-0}"
  echo "GGML_SYCL_FUSE_MMVQ_ADD=${GGML_SYCL_FUSE_MMVQ_ADD:-0}"
  echo "GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8=${GGML_SYCL_FUSE_MMVQ_ADD_RMS_Q8:-0}"
  echo "GGML_SYCL_FUSE_SWIGLU_Q8=${GGML_SYCL_FUSE_SWIGLU_Q8:-0}"
  echo "GGML_SYCL_FUSE_SSM_CONV_SILU=${GGML_SYCL_FUSE_SSM_CONV_SILU:-0}"
  echo "GGML_SYCL_FUSE_SSM_CONV_CACHE=${GGML_SYCL_FUSE_SSM_CONV_CACHE:-0}"
  echo "GGML_SYCL_FUSE_SSM_CONV_QK_NORM=${GGML_SYCL_FUSE_SSM_CONV_QK_NORM:-0}"
  echo "GGML_SYCL_FUSE_GDN_CACHE=${GGML_SYCL_FUSE_GDN_CACHE:-0}"
  echo "GGML_SYCL_FUSE_GDN_RAW_GATES=${GGML_SYCL_FUSE_GDN_RAW_GATES:-0}"
  echo "GGML_SYCL_FUSE_GDN_EPILOGUE=${GGML_SYCL_FUSE_GDN_EPILOGUE:-0}"
  echo "GGML_SYCL_CYCLE_TIMING=${GGML_SYCL_CYCLE_TIMING:-0}"
  echo "LLAMA_MTP_DEVICE_UNROLL=${LLAMA_MTP_DEVICE_UNROLL:-0}"
  echo "GGML_SYCL_ENABLE_DNN=${GGML_SYCL_ENABLE_DNN:-1}"
  echo "GGML_SYCL_ENABLE_OPT=${GGML_SYCL_ENABLE_OPT:-1}"
  echo "GGML_SYCL_ENABLE_VMM=${GGML_SYCL_ENABLE_VMM:-1}"
  echo "GGML_SYCL_XE2_Q4_M6_FFN=${GGML_SYCL_XE2_Q4_M6_FFN:-0}"
  echo "GGML_SYCL_XE2_Q4_M6_PACK_LIMIT=${GGML_SYCL_XE2_Q4_M6_PACK_LIMIT:-0}"
  echo "GGML_SYCL_XE2_Q4_M6_PACK_CACHE=${GGML_SYCL_XE2_Q4_M6_PACK_CACHE:-disabled}"
  echo "GGML_SYCL_XE2_Q4_M6_COMPARE=${GGML_SYCL_XE2_Q4_M6_COMPARE:-0}"
  echo "extra_llama_args=${EXTRA_LLAMA_ARGS:-}"
  echo "target_model=$TARGET_MODEL"
  echo "api_model=$API_MODEL"
} > "$RUN_DIR/identity.env"

GPU_INDEX="$GPU_INDEX" PORT="$PORT" SPEC_PROFILE="$SPEC_PROFILE" \
  MODEL="$TARGET_MODEL" \
  LOG="$RUN_DIR/server.identity.log" \
  CACHE_TYPE_K="${CACHE_TYPE_K:-q8_0}" CACHE_TYPE_V="${CACHE_TYPE_V:-q8_0}" \
  scripts/serve-qwen36-27b-mtp-gguf-llamacpp.sh \
  > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for http://127.0.0.1:${PORT}/v1/models" >&2
    exit 1
  fi
  sleep 2
done

env \
  BASE_URL="http://127.0.0.1:${PORT}" \
  MODEL="$API_MODEL" \
  LABEL="$LABEL" \
  OUT="$OUT" \
  REQUEST_EXTRA_JSON="${REQUEST_EXTRA_JSON:-}" \
  scripts/bench-qwen36-27b-mtp-gguf-realistic.sh \
  > "$RUN_DIR/bench.stdout.log" 2>&1

cp "$OUT" "$RUN_DIR/result.json"
python3 - "$OUT" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path) as f:
    result = json.load(f)
gate = result.get("realistic_final_gate", {})
summary = result.get("summary", {}).get("tok_s_1_100_after_ttft", {})
ttft = result.get("summary", {}).get("ttft_ms", {})
print(json.dumps({
    "path": path,
    "passed": gate.get("passed"),
    "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    "median_tok_s_1_100_after_ttft": summary.get("median"),
    "p10_tok_s_1_100_after_ttft": summary.get("p10"),
    "mean_tok_s_1_100_after_ttft": summary.get("mean"),
    "median_ttft_ms": ttft.get("median"),
}, indent=2))
PY
echo "$OUT"
