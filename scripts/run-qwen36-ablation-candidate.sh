#!/usr/bin/env bash
set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <label>" >&2
  exit 2
fi

LABEL="$1"
ROOT="${ROOT:-/home/steve/llm-optimizations}"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
MODEL_PATH="${MODEL_PATH:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
PORT="${PORT:-18080}"
BASE_URL="${BASE_URL:-http://127.0.0.1:$PORT}"
STAMP="${STAMP:-$(date -u +%Y%m%d%H%M%S)}"
CACHE_LABEL="${CACHE_LABEL:-qwen36-ablation-$LABEL}"
LOG_PATH="${LOG_PATH:-$DATA_DIR/qwen36-ablation-$LABEL-$STAMP.log}"

METRICS_OUT="${METRICS_OUT:-$DATA_DIR/qwen36-ablation-$LABEL-p512o512-$STAMP.json}"
JSON_OUT="${JSON_OUT:-$DATA_DIR/qwen36-ablation-$LABEL-json-repeat${JSON_REPEATS:-96}-$STAMP.json}"
COLOR_OUT="${COLOR_OUT:-$DATA_DIR/qwen36-ablation-$LABEL-color-repeat${COLOR_REPEATS:-96}-$STAMP.json}"
SUMMARY_OUT="${SUMMARY_OUT:-$DATA_DIR/qwen36-ablation-$LABEL-summary-$STAMP.json}"
QUALITY_OUT="${QUALITY_OUT:-$DATA_DIR/qwen36-ablation-$LABEL-quality-suite-$STAMP.json}"

METRICS_REPEATS="${METRICS_REPEATS:-2}"
JSON_REPEATS="${JSON_REPEATS:-96}"
COLOR_REPEATS="${COLOR_REPEATS:-96}"
QUALITY_REPEAT_RUNS="${QUALITY_REPEAT_RUNS:-8}"
QUALITY_LONG_CONTEXT_TOKENS="${QUALITY_LONG_CONTEXT_TOKENS:-4096}"
QUALITY_CHAT_TEMPLATE_KWARGS_JSON="${QUALITY_CHAT_TEMPLATE_KWARGS_JSON:-{\"enable_thinking\": false}}"
JSON_REQUEST_ID_PREFIX="${JSON_REQUEST_ID_PREFIX:-}"
COLOR_REQUEST_ID_PREFIX="${COLOR_REQUEST_ID_PREFIX:-}"
JSON_LOGPROBS="${JSON_LOGPROBS:-0}"
COLOR_LOGPROBS="${COLOR_LOGPROBS:-0}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1800}"
METRICS_PROMPT_KIND="${METRICS_PROMPT_KIND:-preset}"
METRICS_PROMPT_PRESET="${METRICS_PROMPT_PRESET:-natural-chat}"
METRICS_RANDOM_PREFIX_LEN="${METRICS_RANDOM_PREFIX_LEN:-0}"
METRICS_PROMPT_TOKENS="${METRICS_PROMPT_TOKENS:-512}"
METRICS_OUTPUT_TOKENS="${METRICS_OUTPUT_TOKENS:-512}"
METRICS_WARMUP_OUTPUT_TOKENS="${METRICS_WARMUP_OUTPUT_TOKENS:-64}"

mkdir -p "$DATA_DIR"

export MODEL_PATH
export PORT
export LOG_PATH
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-/mnt/fast-ai/vllm-cache-exp/$CACHE_LABEL/torchinductor}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/$CACHE_LABEL/vllm}"
export VLLM_XPU_GDN_NATIVE_FALLBACK="${VLLM_XPU_GDN_NATIVE_FALLBACK:-decode,prefill}"
export VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK="${VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK:-1}"

if [[ "${ABLATION_FAST_GRAPH_AUTOCONFIG:-1}" == "1" ]] \
  && [[ "${VLLM_XPU_GDN_NATIVE_FALLBACK:-}" == "prefill" ]] \
  && [[ "${XPU_GRAPH:-0}" == "1" ]] \
  && [[ "${VLLM_XPU_ENABLE_XPU_GRAPH:-0}" == "1" ]] \
  && [[ "${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-0}" == "1" ]] \
  && [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
fi
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"

SERVER_PID=""

cleanup() {
  local status=$?
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -INT "$SERVER_PID" 2>/dev/null || true
    for _ in $(seq 1 60); do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      kill -TERM "$SERVER_PID" 2>/dev/null || true
    fi
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

check_ready() {
  "$PYTHON" - "$BASE_URL" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(base_url + "/v1/models", timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("data"):
        raise SystemExit(0)
except Exception:
    pass
raise SystemExit(1)
PY
}

run_step() {
  local name="$1"
  shift
  echo "[ablation:$LABEL] running $name"
  "$@"
  local rc=$?
  echo "[ablation:$LABEL] $name rc=$rc"
  return "$rc"
}

echo "[ablation:$LABEL] stamp=$STAMP"
echo "[ablation:$LABEL] log=$LOG_PATH"
echo "[ablation:$LABEL] cache=$CACHE_LABEL"
echo "[ablation:$LABEL] guard env: GDN=${VLLM_XPU_GDN_NATIVE_FALLBACK:-<default>} GDN_PREFILL_FALLBACK=${VLLM_XPU_GDN_NATIVE_PREFILL_FALLBACK:-<default>} GDN_PREFILL_RECURRENT=${VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK:-<default>} GDN_INITIAL_STEPS=${VLLM_XPU_GDN_NATIVE_FALLBACK_INITIAL_DECODE_STEPS:-<default>} GDN_DECODE_LAYERS=${VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_LAYERS:-<default>} GDN_DECODE_MAX_LAYER=${VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_MAX_LAYER:-<default>} GDN_DECODE_LAYER_REGEX=${VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_LAYER_REGEX:-<default>} GDN_SYNC_DECODE=${VLLM_XPU_GDN_SYNC_BEFORE_NATIVE_DECODE:-<default>} GDN_SYNC_DECODE_LAYERS=${VLLM_XPU_GDN_SYNC_BEFORE_NATIVE_DECODE_LAYERS:-<default>} TOPK=${VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK:-<default>} SAMPLE_FALLBACK=${VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK:-<default>} BF16_TOPK_FASTPATH=${VLLM_XPU_GREEDY_SAMPLE_BF16_TOPK_FASTPATH:-<default>} LOGITS_NAN_SANITIZE=${VLLM_XPU_SANITIZE_LOGITS_NAN:-<default>} LOCAL_ARGMAX=${VLLM_XPU_LOCAL_ARGMAX_DECODE:-<default>} LOCAL_ARGMAX_DIRECT=${VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER:-<default>} LOCAL_ARGMAX_DIRECT_REUSE=${VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER_REUSE:-<default>} LOCAL_ARGMAX_PACKED=${VLLM_XPU_LOCAL_ARGMAX_PACKED_GATHER:-<default>} LOCAL_ARGMAX_SYNC=${VLLM_XPU_LOCAL_ARGMAX_SYNC_TOKENS:-<default>} DUMMY_LOGIT_STATIC=${VLLM_XPU_DUMMY_LOGIT_INDICES_STATIC:-<default>} PREFILL_REPLAY_OFF=${VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY:-<default>} ZERO_ALL_PREFILL_GDN=${VLLM_XPU_ZERO_ALL_PREFILL_GDN_STATE:-<default>} ZERO_FRESH_GDN=${VLLM_XPU_ZERO_FRESH_GDN_STATE:-<default>} PACKED_DECODE=${VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE:-<default>} XPU_GRAPH=${XPU_GRAPH:-<default>} VLLM_XPU_GRAPH=${VLLM_XPU_ENABLE_XPU_GRAPH:-<default>} FORCE_GRAPH_COMM=${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-<default>} NOOP_COMM_CAPTURE=${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-<default>} CUSTOM_COLLECTIVES=${VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES:-<default>} COMPILE_ALLREDUCE_CUSTOM=${VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP:-<default>} CUSTOM_AR_GRAPH_CLONE=${VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT:-<default>} CUSTOM_AR_CLONE=${VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT:-<default>} REPLAY_MAX_PIECE=${VLLM_XPU_CUDAGRAPH_REPLAY_MAX_PIECEWISE_INDEX:-<default>} DISABLE_SUBMOD=${VLLM_XPU_CUDAGRAPH_DISABLE_SUBMOD_REGEX:-<default>} RECAPTURE_AFTER=${VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS:-<default>} RECAPTURE_REGEX=${VLLM_XPU_CUDAGRAPH_RECAPTURE_REGEX:-<default>} GRAPH_STRONG_OUTPUT=${VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT:-<default>} GRAPH_PER_WRAPPER_POOL=${VLLM_XPU_CUDAGRAPH_PER_WRAPPER_POOL:-<default>} GRAPH_NO_GLOBAL_POOL=${VLLM_XPU_CUDAGRAPH_NO_GLOBAL_POOL:-<default>} EAGER_EVERY_REQUESTS=${VLLM_XPU_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS:-<default>} ALLOW_RUNTIME_RECAPTURE=${VLLM_XPU_CUDAGRAPH_ALLOW_RUNTIME_RECAPTURE:-<default>} SYNC_REPLAY=${VLLM_XPU_SYNC_CUDAGRAPH_REPLAY:-<default>} TRACE_FILE=${VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_FILE:-<default>} TRACE_SUBMOD=${VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_SUBMOD_REGEX:-<default>} TRACE_RANK=${VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_RANK:-<default>} TRACE_INPUTS=${VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_INPUTS:-<default>} TRACE_DIGEST=${VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_DIGEST:-<default>} ZERO_REPLAY_REGEX=${VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX:-<default>} ZERO_REPLAY_INDICES=${VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES:-<default>} CLONE_REPLAY_REGEX=${VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_REGEX:-<default>} CLONE_REPLAY_INDICES=${VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_INDICES:-<default>} STATIC_INPUT_REGEX=${VLLM_XPU_CUDAGRAPH_STATIC_INPUT_REGEX:-<default>} STATIC_INPUT_INDICES=${VLLM_XPU_CUDAGRAPH_STATIC_INPUT_INDICES:-<default>} STATIC_INPUT_MAX=${VLLM_XPU_CUDAGRAPH_STATIC_INPUT_MAX_NUMEL:-<default>} COMPARE_DIRECT_REGEX=${VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX:-<default>} COMPARE_DIRECT_RETURN=${VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_RETURN_DIRECT:-<default>} W8A8_ALLOW=${VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW:-<default>} W8A8_OFFSETS=${VLLM_XPU_W8A8_USE_OFFSETS:-<default>} W8A8_PREFIX=${VLLM_XPU_W8A8_OFFSETS_PREFIX_OP:-<default>} W8A8_LAYERLET=${VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET:-<default>} INT8_MIXED_WS=${VLLM_XPU_INT8_MOE_MIXED_WORKSPACE:-<default>} INT8_PERSIST_WS=${VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH:-<default>} XPU_SHARED_EXP=${VLLM_XPU_SHARED_EXPERTS_STREAM:-<default>} XPU_SHARED_FUSED_ACT_QUANT=${VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT:-<default>} XPU_SHARED_ADD_AR=${VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP:-<default>} GMEM=${GPU_MEMORY_UTILIZATION:-<default>} COMPILATION_CONFIG=${COMPILATION_CONFIG:-<default>} FAST_GRAPH_AUTOCONFIG=${ABLATION_FAST_GRAPH_AUTOCONFIG:-1} EXTRA_ARGS=${VLLM_EXTRA_ARGS:-<default>}"

echo "[ablation:$LABEL] fused-prologue: OFFSET=${VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET:-<unset>} ALLOW_CAPTURE=${VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE:-<unset>} SKIP_LAYERS=${VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_SKIP_LAYERS:-<unset>} LAYER_REGEX=${VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_LAYER_REGEX:-<unset>}"
echo "[ablation:$LABEL] server_launcher=${SERVER_LAUNCHER:-launch-qwen36-quark-int8-accepted.sh}"

"${SERVER_LAUNCHER:-/home/steve/llm-optimizations/scripts/launch-qwen36-quark-int8-accepted.sh}" &
SERVER_PID=$!

ready=0
for elapsed in $(seq 1 "$READINESS_TIMEOUT_S"); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[ablation:$LABEL] server exited before readiness" >&2
    tail -n 120 "$LOG_PATH" >&2 || true
    exit 1
  fi
  if check_ready; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" != "1" ]]; then
  echo "[ablation:$LABEL] server was not ready after ${READINESS_TIMEOUT_S}s" >&2
  tail -n 160 "$LOG_PATH" >&2 || true
  exit 1
fi

metrics_rc=0
json_rc=0
color_rc=0
quality_rc=0

if [[ "${ABLATION_SKIP_METRICS:-0}" != "1" ]]; then
  run_step metrics "$PYTHON" "$ROOT/scripts/measure-openai-endpoint-metrics.py" \
    --base-url "$BASE_URL" \
    --tokenizer "$MODEL_PATH" \
    --prompt-kind "$METRICS_PROMPT_KIND" \
    --prompt-preset "$METRICS_PROMPT_PRESET" \
    --random-prefix-len "$METRICS_RANDOM_PREFIX_LEN" \
    --prompt-tokens "$METRICS_PROMPT_TOKENS" \
    --output-tokens "$METRICS_OUTPUT_TOKENS" \
    --warmup-output-tokens "$METRICS_WARMUP_OUTPUT_TOKENS" \
    --repeats "$METRICS_REPEATS" \
    --ignore-eos \
    --skip-vram \
    --out "$METRICS_OUT"
  metrics_rc=$?
fi

if [[ "${ABLATION_SKIP_CANARIES:-0}" != "1" ]]; then
  json_request_id_args=()
  if [[ -n "$JSON_REQUEST_ID_PREFIX" ]]; then
    json_request_id_args=(--request-id-prefix "$JSON_REQUEST_ID_PREFIX")
  fi
  json_logprobs_args=()
  if [[ "$JSON_LOGPROBS" != "0" ]]; then
    json_logprobs_args=(--logprobs "$JSON_LOGPROBS")
  fi
  run_step json-canary "$PYTHON" "$ROOT/scripts/probe-fixed-chatml-completion-repeat.py" \
    --base-url "$BASE_URL" \
    --tokenizer "$MODEL_PATH" \
    --case json \
    --repeats "$JSON_REPEATS" \
    --stop-on-mismatch \
    "${json_request_id_args[@]}" \
    "${json_logprobs_args[@]}" \
    --output-json "$JSON_OUT"
  json_rc=$?

  color_request_id_args=()
  if [[ -n "$COLOR_REQUEST_ID_PREFIX" ]]; then
    color_request_id_args=(--request-id-prefix "$COLOR_REQUEST_ID_PREFIX")
  fi
  color_logprobs_args=()
  if [[ "$COLOR_LOGPROBS" != "0" ]]; then
    color_logprobs_args=(--logprobs "$COLOR_LOGPROBS")
  fi
  run_step color-canary "$PYTHON" "$ROOT/scripts/probe-fixed-chatml-completion-repeat.py" \
    --base-url "$BASE_URL" \
    --tokenizer "$MODEL_PATH" \
    --case color \
    --repeats "$COLOR_REPEATS" \
    --stop-on-mismatch \
    "${color_request_id_args[@]}" \
    "${color_logprobs_args[@]}" \
    --output-json "$COLOR_OUT"
  color_rc=$?
fi

if [[ "${ABLATION_RUN_QUALITY:-0}" == "1" ]]; then
  run_step quality-suite "$PYTHON" "$ROOT/scripts/qwen36-text-quality-suite.py" \
    --base-url "$BASE_URL" \
    --tokenizer "$MODEL_PATH" \
    --repeat-runs "$QUALITY_REPEAT_RUNS" \
    --long-context-tokens "$QUALITY_LONG_CONTEXT_TOKENS" \
    --chat-template-kwargs-json "$QUALITY_CHAT_TEMPLATE_KWARGS_JSON" \
    --output-json "$QUALITY_OUT"
  quality_rc=$?
fi

"$PYTHON" - "$SUMMARY_OUT" "$LABEL" "$STAMP" "$metrics_rc" "$json_rc" "$color_rc" "$quality_rc" "$METRICS_OUT" "$JSON_OUT" "$COLOR_OUT" "$QUALITY_OUT" "$LOG_PATH" <<'PY'
import json
import os
import sys
from pathlib import Path

summary_out, label, stamp, metrics_rc, json_rc, color_rc, quality_rc, metrics_path, json_path, color_path, quality_path, log_path = sys.argv[1:]

def read_json(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())

def artifact_status(requested, rc, path):
    exists = Path(path).exists()
    if not requested:
        return "skipped"
    if int(rc) != 0:
        return "failed"
    if not exists:
        return "missing_artifact"
    return "passed"

def summary_mean(summary, key):
    try:
        value = ((summary or {}).get(key) or {}).get("mean")
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None

def canary_summary(data):
    if not data:
        return None
    return {
        "pass_all": data.get("pass_all"),
        "repeats_completed": data.get("repeats_completed"),
        "mismatch_count": data.get("mismatch_count"),
        "first_mismatch": (data.get("mismatches") or [None])[0],
    }

metrics = read_json(metrics_path)
json_canary = read_json(json_path)
color_canary = read_json(color_path)
quality = read_json(quality_path)

metrics_requested = os.environ.get("ABLATION_SKIP_METRICS", "0") != "1"
canaries_requested = os.environ.get("ABLATION_SKIP_CANARIES", "0") != "1"
quality_requested = os.environ.get("ABLATION_RUN_QUALITY", "0") == "1"

out = {
    "label": label,
    "stamp": stamp,
    "return_codes": {
        "metrics": int(metrics_rc),
        "json_canary": int(json_rc),
        "color_canary": int(color_rc),
        "quality_suite": int(quality_rc),
    },
    "status": {
        "metrics": artifact_status(metrics_requested, metrics_rc, metrics_path),
        "json_canary": artifact_status(canaries_requested, json_rc, json_path),
        "color_canary": artifact_status(canaries_requested, color_rc, color_path),
        "quality_suite": artifact_status(quality_requested, quality_rc, quality_path),
    },
    "artifacts": {
        "metrics": metrics_path,
        "json_canary": json_path,
        "color_canary": color_path,
        "quality_suite": quality_path,
        "log": log_path,
    },
    "artifact_exists": {
        "metrics": Path(metrics_path).exists(),
        "json_canary": Path(json_path).exists(),
        "color_canary": Path(color_path).exists(),
        "quality_suite": Path(quality_path).exists(),
        "log": Path(log_path).exists(),
    },
    "env": {
        "VLLM_XPU_GDN_NATIVE_FALLBACK": os.environ.get("VLLM_XPU_GDN_NATIVE_FALLBACK"),
        "VLLM_XPU_GDN_NATIVE_PREFILL_FALLBACK": os.environ.get("VLLM_XPU_GDN_NATIVE_PREFILL_FALLBACK"),
        "VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK": os.environ.get("VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK"),
        "VLLM_XPU_GDN_NATIVE_FALLBACK_INITIAL_DECODE_STEPS": os.environ.get("VLLM_XPU_GDN_NATIVE_FALLBACK_INITIAL_DECODE_STEPS"),
        "VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_LAYERS": os.environ.get("VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_LAYERS"),
        "VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_MAX_LAYER": os.environ.get("VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_MAX_LAYER"),
        "VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_LAYER_REGEX": os.environ.get("VLLM_XPU_GDN_NATIVE_FALLBACK_DECODE_LAYER_REGEX"),
        "VLLM_XPU_GDN_SYNC_BEFORE_NATIVE_DECODE": os.environ.get("VLLM_XPU_GDN_SYNC_BEFORE_NATIVE_DECODE"),
        "VLLM_XPU_GDN_SYNC_BEFORE_NATIVE_DECODE_LAYERS": os.environ.get("VLLM_XPU_GDN_SYNC_BEFORE_NATIVE_DECODE_LAYERS"),
        "VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK": os.environ.get("VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK"),
        "VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK": os.environ.get("VLLM_XPU_GREEDY_SAMPLE_XPU_FALLBACK"),
        "VLLM_XPU_GREEDY_SAMPLE_BF16_TOPK_FASTPATH": os.environ.get("VLLM_XPU_GREEDY_SAMPLE_BF16_TOPK_FASTPATH"),
        "VLLM_XPU_ASYNC_CLONE_SAMPLED_TOKEN_IDS": os.environ.get("VLLM_XPU_ASYNC_CLONE_SAMPLED_TOKEN_IDS"),
        "VLLM_XPU_SANITIZE_LOGITS_NAN": os.environ.get("VLLM_XPU_SANITIZE_LOGITS_NAN"),
        "VLLM_XPU_LOCAL_ARGMAX_DECODE": os.environ.get("VLLM_XPU_LOCAL_ARGMAX_DECODE"),
        "VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER": os.environ.get("VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER"),
        "VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER_REUSE": os.environ.get("VLLM_XPU_LOCAL_ARGMAX_DIRECT_GATHER_REUSE"),
        "VLLM_XPU_LOCAL_ARGMAX_PACKED_GATHER": os.environ.get("VLLM_XPU_LOCAL_ARGMAX_PACKED_GATHER"),
        "VLLM_XPU_LOCAL_ARGMAX_SYNC_TOKENS": os.environ.get("VLLM_XPU_LOCAL_ARGMAX_SYNC_TOKENS"),
        "VLLM_XPU_DUMMY_LOGIT_INDICES_STATIC": os.environ.get("VLLM_XPU_DUMMY_LOGIT_INDICES_STATIC"),
        "VLLM_XPU_ZERO_ALL_PREFILL_GDN_STATE": os.environ.get("VLLM_XPU_ZERO_ALL_PREFILL_GDN_STATE"),
        "VLLM_XPU_ZERO_FRESH_GDN_STATE": os.environ.get("VLLM_XPU_ZERO_FRESH_GDN_STATE"),
        "VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY": os.environ.get("VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY"),
        "VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE": os.environ.get("VLLM_ENABLE_FLA_PACKED_RECURRENT_DECODE"),
        "XPU_GRAPH": os.environ.get("XPU_GRAPH"),
        "VLLM_XPU_ENABLE_XPU_GRAPH": os.environ.get("VLLM_XPU_ENABLE_XPU_GRAPH"),
        "VLLM_XPU_FORCE_GRAPH_WITH_COMM": os.environ.get("VLLM_XPU_FORCE_GRAPH_WITH_COMM"),
        "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE": os.environ.get("VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE"),
        "VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES": os.environ.get("VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES"),
        "VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP": os.environ.get("VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP"),
        "VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT": os.environ.get("VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT"),
        "VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT": os.environ.get("VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_MAX_PIECEWISE_INDEX": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_MAX_PIECEWISE_INDEX"),
        "VLLM_XPU_CUDAGRAPH_DISABLE_SUBMOD_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_DISABLE_SUBMOD_REGEX"),
        "VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS": os.environ.get("VLLM_XPU_CUDAGRAPH_RECAPTURE_AFTER_N_REPLAYS"),
        "VLLM_XPU_CUDAGRAPH_RECAPTURE_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_RECAPTURE_REGEX"),
        "VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT": os.environ.get("VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT"),
        "VLLM_XPU_CUDAGRAPH_PER_WRAPPER_POOL": os.environ.get("VLLM_XPU_CUDAGRAPH_PER_WRAPPER_POOL"),
        "VLLM_XPU_CUDAGRAPH_NO_GLOBAL_POOL": os.environ.get("VLLM_XPU_CUDAGRAPH_NO_GLOBAL_POOL"),
        "VLLM_XPU_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS": os.environ.get("VLLM_XPU_DECODE_CUDAGRAPH_REPLAY_EAGER_EVERY_N_REQUESTS"),
        "VLLM_XPU_CUDAGRAPH_ALLOW_RUNTIME_RECAPTURE": os.environ.get("VLLM_XPU_CUDAGRAPH_ALLOW_RUNTIME_RECAPTURE"),
        "VLLM_XPU_SYNC_CUDAGRAPH_REPLAY": os.environ.get("VLLM_XPU_SYNC_CUDAGRAPH_REPLAY"),
        "VLLM_XPU_CUDAGRAPH_SANITIZE_REPLAY_INPUTS": os.environ.get("VLLM_XPU_CUDAGRAPH_SANITIZE_REPLAY_INPUTS"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_FILE": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_FILE"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_MAX_LINES": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_MAX_LINES"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_RANK": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_RANK"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_SUBMOD_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_SUBMOD_REGEX"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_REQ_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_REQ_REGEX"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_INPUTS": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_INPUTS"),
        "VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_DIGEST": os.environ.get("VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_DIGEST"),
        "VLLM_XPU_GDN_TRACE_FILE": os.environ.get("VLLM_XPU_GDN_TRACE_FILE"),
        "VLLM_XPU_GDN_TRACE_MAX_LINES": os.environ.get("VLLM_XPU_GDN_TRACE_MAX_LINES"),
        "VLLM_XPU_GDN_TRACE_RANK": os.environ.get("VLLM_XPU_GDN_TRACE_RANK"),
        "VLLM_XPU_GDN_TRACE_LAYER_REGEX": os.environ.get("VLLM_XPU_GDN_TRACE_LAYER_REGEX"),
        "VLLM_XPU_GDN_TRACE_REQ_REGEX": os.environ.get("VLLM_XPU_GDN_TRACE_REQ_REGEX"),
        "VLLM_XPU_GDN_TRACE_PREFILL_ONLY": os.environ.get("VLLM_XPU_GDN_TRACE_PREFILL_ONLY"),
        "VLLM_XPU_GDN_TRACE_DECODE_ONLY": os.environ.get("VLLM_XPU_GDN_TRACE_DECODE_ONLY"),
        "VLLM_XPU_GDN_TRACE_TENSOR_LIMIT": os.environ.get("VLLM_XPU_GDN_TRACE_TENSOR_LIMIT"),
        "VLLM_XPU_GDN_TRACE_STATE_LIMIT": os.environ.get("VLLM_XPU_GDN_TRACE_STATE_LIMIT"),
        "VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX"),
        "VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES": os.environ.get("VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES"),
        "VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_REGEX"),
        "VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_INDICES": os.environ.get("VLLM_XPU_CUDAGRAPH_CLONE_REPLAY_OUTPUT_INDICES"),
        "VLLM_XPU_CUDAGRAPH_STATIC_INPUT_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_STATIC_INPUT_REGEX"),
        "VLLM_XPU_CUDAGRAPH_STATIC_INPUT_INDICES": os.environ.get("VLLM_XPU_CUDAGRAPH_STATIC_INPUT_INDICES"),
        "VLLM_XPU_CUDAGRAPH_STATIC_INPUT_MAX_NUMEL": os.environ.get("VLLM_XPU_CUDAGRAPH_STATIC_INPUT_MAX_NUMEL"),
        "VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX": os.environ.get("VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX"),
        "VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_RETURN_DIRECT": os.environ.get("VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_RETURN_DIRECT"),
        "VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW": os.environ.get("VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW"),
        "VLLM_XPU_W8A8_USE_OFFSETS": os.environ.get("VLLM_XPU_W8A8_USE_OFFSETS"),
        "VLLM_XPU_W8A8_OFFSETS_PREFIX_OP": os.environ.get("VLLM_XPU_W8A8_OFFSETS_PREFIX_OP"),
        "VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET": os.environ.get("VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET"),
        "VLLM_XPU_INT8_MOE_MIXED_WORKSPACE": os.environ.get("VLLM_XPU_INT8_MOE_MIXED_WORKSPACE"),
        "VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH": os.environ.get("VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH"),
        "VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET": os.environ.get("VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET"),
        "VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE": os.environ.get("VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE"),
        "VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_SKIP_LAYERS": os.environ.get("VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_SKIP_LAYERS"),
        "VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_LAYER_REGEX": os.environ.get("VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_LAYER_REGEX"),
        "VLLM_XPU_SHARED_EXPERTS_STREAM": os.environ.get("VLLM_XPU_SHARED_EXPERTS_STREAM"),
        "VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT": os.environ.get("VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT"),
        "VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP": os.environ.get("VLLM_XPU_MOE_SHARED_ADD_ALLREDUCE_CUSTOM_OP"),
        "VLLM_XPU_METADATA_COPY_ALLOW": os.environ.get("VLLM_XPU_METADATA_COPY_ALLOW"),
        "VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT": os.environ.get("VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT"),
        "VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY": os.environ.get("VLLM_XPU_BLOCK_TABLE_DIRTY_COMMIT_LOG_EVERY"),
        "GPU_MEMORY_UTILIZATION": os.environ.get("GPU_MEMORY_UTILIZATION"),
        "COMPILATION_CONFIG": os.environ.get("COMPILATION_CONFIG"),
        "ABLATION_FAST_GRAPH_AUTOCONFIG": os.environ.get("ABLATION_FAST_GRAPH_AUTOCONFIG", "1"),
        "VLLM_EXTRA_ARGS": os.environ.get("VLLM_EXTRA_ARGS"),
        "METRICS_PROMPT_KIND": os.environ.get("METRICS_PROMPT_KIND"),
        "METRICS_PROMPT_PRESET": os.environ.get("METRICS_PROMPT_PRESET"),
        "METRICS_RANDOM_PREFIX_LEN": os.environ.get("METRICS_RANDOM_PREFIX_LEN"),
        "METRICS_PROMPT_TOKENS": os.environ.get("METRICS_PROMPT_TOKENS"),
        "METRICS_OUTPUT_TOKENS": os.environ.get("METRICS_OUTPUT_TOKENS"),
        "METRICS_WARMUP_OUTPUT_TOKENS": os.environ.get("METRICS_WARMUP_OUTPUT_TOKENS"),
        "JSON_LOGPROBS": os.environ.get("JSON_LOGPROBS"),
        "COLOR_LOGPROBS": os.environ.get("COLOR_LOGPROBS"),
    },
}

if metrics:
    metrics_summary = metrics.get("summary", {})
    out["metrics_summary"] = metrics_summary
    out["speed"] = {
        "tok_s_out_corrected_mean": summary_mean(
            metrics_summary, "tok_s_out_client_after_first_chunk_corrected"
        ),
        "tok_s_out_after_first_chunk_mean": summary_mean(
            metrics_summary, "tok_s_out_client_after_first_chunk"
        ),
        "tok_s_out_e2e_mean": summary_mean(
            metrics_summary, "tok_s_out_client_e2e"
        ),
        "decode_ms_per_token_mean": summary_mean(
            metrics_summary, "decode_ms_per_generation_token_vllm_histogram"
        ),
        "ttft_ms_client_mean": summary_mean(metrics_summary, "ttft_ms_client"),
    }
if json_canary:
    out["json_canary"] = canary_summary(json_canary)
if color_canary:
    out["color_canary"] = canary_summary(color_canary)
if quality:
    out["quality_suite"] = {
        "pass_all": quality.get("pass_all"),
        "baseline_match_all": quality.get("baseline_match_all"),
        "exact": {item.get("name"): item.get("pass") for item in quality.get("exact_cases", [])},
        "repeat_pass": (quality.get("repeat_case") or {}).get("pass"),
        "long_context_pass": (quality.get("long_context_case") or {}).get("pass"),
    }

gate_failures = []
if metrics_requested and out["status"]["metrics"] != "passed":
    gate_failures.append("metrics")
if canaries_requested:
    if out["status"]["json_canary"] != "passed" or not (out.get("json_canary") or {}).get("pass_all"):
        gate_failures.append("json_canary")
    if out["status"]["color_canary"] != "passed" or not (out.get("color_canary") or {}).get("pass_all"):
        gate_failures.append("color_canary")
if quality_requested:
    quality_out = out.get("quality_suite") or {}
    if out["status"]["quality_suite"] != "passed" or not quality_out.get("pass_all") or not quality_out.get("baseline_match_all"):
        gate_failures.append("quality_suite")

out["decision"] = {
    "accepted_by_requested_gates": not gate_failures,
    "gate_failures": gate_failures,
}

Path(summary_out).write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({
    "summary": summary_out,
    "metrics_rc": int(metrics_rc),
    "json_rc": int(json_rc),
    "color_rc": int(color_rc),
    "quality_rc": int(quality_rc),
    "status": out["status"],
    "decision": out["decision"],
    "speed": out.get("speed"),
}, sort_keys=True))
PY

echo "[ablation:$LABEL] summary=$SUMMARY_OUT"
exit 0
