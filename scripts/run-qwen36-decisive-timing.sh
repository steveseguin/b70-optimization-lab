#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/steve/llm-optimizations}"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_PATH="${MODEL_PATH:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
PORT="${PORT:-18080}"
BASE_URL="${BASE_URL:-http://127.0.0.1:$PORT}"
LABEL="${1:-accepted-c1-decisive-timing}"
STAMP="${STAMP:-$(date -u +%Y%m%d%H%M%S)}"
LOG_PATH="${LOG_PATH:-$DATA_DIR/qwen36-$LABEL-$STAMP.log}"
METRICS_OUT="${METRICS_OUT:-$DATA_DIR/qwen36-$LABEL-p${PROMPT_TOKENS:-512}o${OUTPUT_TOKENS:-256}-$STAMP.json}"
TIMING_SUMMARY_OUT="${TIMING_SUMMARY_OUT:-$DATA_DIR/qwen36-$LABEL-timing-summary-$STAMP.json}"
DECISION_JSON="${DECISION_JSON:-$DATA_DIR/qwen36-$LABEL-timing-decision-$STAMP.json}"
DECISION_MD="${DECISION_MD:-$DATA_DIR/qwen36-$LABEL-timing-decision-$STAMP.md}"
JSON_OUT="${JSON_OUT:-$DATA_DIR/qwen36-$LABEL-json-repeat${JSON_REPEATS:-32}-$STAMP.json}"
COLOR_OUT="${COLOR_OUT:-$DATA_DIR/qwen36-$LABEL-color-repeat${COLOR_REPEATS:-32}-$STAMP.json}"
SUMMARY_OUT="${SUMMARY_OUT:-$DATA_DIR/qwen36-$LABEL-run-summary-$STAMP.json}"

PROMPT_TOKENS="${PROMPT_TOKENS:-512}"
OUTPUT_TOKENS="${OUTPUT_TOKENS:-256}"
METRICS_REPEATS="${METRICS_REPEATS:-1}"
WARMUP_OUTPUT_TOKENS="${WARMUP_OUTPUT_TOKENS:-64}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1800}"
RUN_CANARIES="${RUN_CANARIES:-0}"
JSON_REPEATS="${JSON_REPEATS:-32}"
COLOR_REPEATS="${COLOR_REPEATS:-32}"

mkdir -p "$DATA_DIR"

export PORT
export LOG_PATH
export MODEL_PATH
export CACHE_LABEL="${CACHE_LABEL:-qwen36-$LABEL}"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-/mnt/fast-ai/vllm-cache-exp/$CACHE_LABEL/torchinductor}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/$CACHE_LABEL/vllm}"

export VLLM_XPU_DECODE_TIMING_ALLOW=1
export VLLM_XPU_DECODE_TIMING="${VLLM_XPU_DECODE_TIMING:-1}"
export VLLM_XPU_DECODE_TIMING_SYNC="${VLLM_XPU_DECODE_TIMING_SYNC:-0}"
export VLLM_XPU_DECODE_TIMING_SUMMARY="${VLLM_XPU_DECODE_TIMING_SUMMARY:-1}"
export VLLM_XPU_DECODE_TIMING_STEP_SUMMARY="${VLLM_XPU_DECODE_TIMING_STEP_SUMMARY:-1}"
export VLLM_XPU_DECODE_TIMING_SKIP_FIRST="${VLLM_XPU_DECODE_TIMING_SKIP_FIRST:-32}"
export VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST="${VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST:-32}"
export VLLM_XPU_DECODE_TIMING_STEP_EVERY="${VLLM_XPU_DECODE_TIMING_STEP_EVERY:-16}"
export VLLM_XPU_DECODE_TIMING_PRINT_EVERY="${VLLM_XPU_DECODE_TIMING_PRINT_EVERY:-0}"

SERVER_PID=""

cleanup() {
  local status=$?
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill -INT "$SERVER_PID" 2>/dev/null || true
    for _ in $(seq 1 90); do
      if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        break
      fi
      sleep 1
    done
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      kill -TERM "$SERVER_PID" 2>/dev/null || true
      sleep 2
    fi
    if kill -0 "$SERVER_PID" 2>/dev/null; then
      kill -KILL "$SERVER_PID" 2>/dev/null || true
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

echo "[timing:$LABEL] stamp=$STAMP"
echo "[timing:$LABEL] log=$LOG_PATH"
echo "[timing:$LABEL] metrics=$METRICS_OUT"
echo "[timing:$LABEL] timing_summary=$TIMING_SUMMARY_OUT"
echo "[timing:$LABEL] decision=$DECISION_JSON"

"$ROOT/scripts/launch-qwen36-quark-int8-accepted.sh" &
SERVER_PID=$!

ready=0
for _elapsed in $(seq 1 "$READINESS_TIMEOUT_S"); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[timing:$LABEL] server exited before readiness" >&2
    tail -n 160 "$LOG_PATH" >&2 || true
    exit 1
  fi
  if check_ready; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" != "1" ]]; then
  echo "[timing:$LABEL] server was not ready after ${READINESS_TIMEOUT_S}s" >&2
  tail -n 160 "$LOG_PATH" >&2 || true
  exit 1
fi

"$PYTHON" "$ROOT/scripts/measure-openai-endpoint-metrics.py" \
  --base-url "$BASE_URL" \
  --tokenizer "$MODEL_PATH" \
  --prompt-kind preset \
  --prompt-preset natural-chat \
  --prompt-tokens "$PROMPT_TOKENS" \
  --output-tokens "$OUTPUT_TOKENS" \
  --warmup-output-tokens "$WARMUP_OUTPUT_TOKENS" \
  --repeats "$METRICS_REPEATS" \
  --ignore-eos \
  --skip-vram \
  --out "$METRICS_OUT"

if [[ "$RUN_CANARIES" == "1" ]]; then
  "$PYTHON" "$ROOT/scripts/probe-fixed-chatml-completion-repeat.py" \
    --base-url "$BASE_URL" \
    --tokenizer "$MODEL_PATH" \
    --case json \
    --repeats "$JSON_REPEATS" \
    --stop-on-mismatch \
    --output-json "$JSON_OUT"
  "$PYTHON" "$ROOT/scripts/probe-fixed-chatml-completion-repeat.py" \
    --base-url "$BASE_URL" \
    --tokenizer "$MODEL_PATH" \
    --case color \
    --repeats "$COLOR_REPEATS" \
    --stop-on-mismatch \
    --output-json "$COLOR_OUT"
fi

kill -INT "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""

"$PYTHON" "$ROOT/scripts/summarize-xpu-decode-timing-log.py" \
  --log "$LOG_PATH" \
  --out "$TIMING_SUMMARY_OUT" \
  --all-lines

"$PYTHON" "$ROOT/scripts/qwen36-timing-family-decision.py" \
  --summary "$TIMING_SUMMARY_OUT" \
  --metrics "$METRICS_OUT" \
  --out-json "$DECISION_JSON" \
  --out-md "$DECISION_MD"

"$PYTHON" - "$SUMMARY_OUT" "$LABEL" "$STAMP" "$LOG_PATH" "$METRICS_OUT" "$TIMING_SUMMARY_OUT" "$DECISION_JSON" "$DECISION_MD" "$RUN_CANARIES" "$JSON_OUT" "$COLOR_OUT" <<'PY'
import json
import os
import sys
from pathlib import Path

(
    out_path,
    label,
    stamp,
    log_path,
    metrics_path,
    timing_summary_path,
    decision_path,
    decision_md_path,
    run_canaries,
    json_path,
    color_path,
) = sys.argv[1:]

payload = {
    "label": label,
    "stamp": stamp,
    "artifacts": {
        "log": log_path,
        "metrics": metrics_path,
        "timing_summary": timing_summary_path,
        "timing_decision_json": decision_path,
        "timing_decision_md": decision_md_path,
    },
    "canaries_requested": run_canaries == "1",
    "env": {
        "COMPILATION_CONFIG": os.environ.get("COMPILATION_CONFIG"),
        "XPU_GRAPH": os.environ.get("XPU_GRAPH"),
        "VLLM_XPU_ENABLE_XPU_GRAPH": os.environ.get("VLLM_XPU_ENABLE_XPU_GRAPH"),
        "VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW": os.environ.get("VLLM_XPU_W8A8_EXPERIMENTAL_ALLOW"),
        "VLLM_XPU_W8A8_USE_OFFSETS": os.environ.get("VLLM_XPU_W8A8_USE_OFFSETS"),
        "VLLM_XPU_W8A8_OFFSETS_PREFIX_OP": os.environ.get("VLLM_XPU_W8A8_OFFSETS_PREFIX_OP"),
        "VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET": os.environ.get("VLLM_XPU_MOE_W8A8_MIDDLE_LAYERLET"),
        "VLLM_XPU_MOE_W8A8_FULL_LAYERLET": os.environ.get("VLLM_XPU_MOE_W8A8_FULL_LAYERLET"),
        "VLLM_XPU_MOE_W8A8_FUSED_Q1": os.environ.get("VLLM_XPU_MOE_W8A8_FUSED_Q1"),
        "VLLM_XPU_MOE_W8A8_FAST_GATHER": os.environ.get("VLLM_XPU_MOE_W8A8_FAST_GATHER"),
        "VLLM_XPU_MOE_W8A8_DIRECT_GEMM2_GATHER": os.environ.get("VLLM_XPU_MOE_W8A8_DIRECT_GEMM2_GATHER"),
        "VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER": os.environ.get("VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER"),
        "VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER_NTILE": os.environ.get("VLLM_XPU_MOE_W8A8_DPAS_GEMM2_GATHER_NTILE"),
        "VLLM_XPU_MOE_W8A8_WORKSPACE_ATOMIC": os.environ.get("VLLM_XPU_MOE_W8A8_WORKSPACE_ATOMIC"),
        "VLLM_XPU_MOE_W8A8_ROUTE_GEMM1": os.environ.get("VLLM_XPU_MOE_W8A8_ROUTE_GEMM1"),
        "VLLM_XPU_MOE_W8A8_ROUTE_GEMM1_MTILE": os.environ.get("VLLM_XPU_MOE_W8A8_ROUTE_GEMM1_MTILE"),
        "VLLM_XPU_INT8_MOE_MIXED_WORKSPACE": os.environ.get("VLLM_XPU_INT8_MOE_MIXED_WORKSPACE"),
        "VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH": os.environ.get("VLLM_XPU_INT8_MOE_PERSISTENT_SCRATCH"),
        "VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET": os.environ.get("VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET"),
        "VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE": os.environ.get("VLLM_XPU_INT8_MOE_FUSED_PROLOGUE_OFFSET_ALLOW_CAPTURE"),
        "VLLM_XPU_SHARED_EXPERTS_STREAM": os.environ.get("VLLM_XPU_SHARED_EXPERTS_STREAM"),
        "VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT": os.environ.get("VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT"),
        "VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT_OUT": os.environ.get("VLLM_XPU_SHARED_EXPERT_FUSED_ACT_QUANT_OUT"),
        "VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT": os.environ.get("VLLM_XPU_SHARED_EXPERT_BOUNDARY_OUT"),
        "VLLM_XPU_DECODE_TIMING_LABEL_REGEX": os.environ.get("VLLM_XPU_DECODE_TIMING_LABEL_REGEX"),
        "VLLM_EXTRA_ARGS": os.environ.get("VLLM_EXTRA_ARGS"),
        "GPU_MEMORY_UTILIZATION": os.environ.get("GPU_MEMORY_UTILIZATION"),
    },
}
if run_canaries == "1":
    payload["artifacts"]["json_canary"] = json_path
    payload["artifacts"]["color_canary"] = color_path
for key in ("metrics", "timing_decision_json"):
    path = Path(payload["artifacts"][key])
    if path.exists():
        payload[key] = json.loads(path.read_text(encoding="utf-8"))
Path(out_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"summary": out_path}, sort_keys=True))
PY

echo "[timing:$LABEL] summary=$SUMMARY_OUT"
