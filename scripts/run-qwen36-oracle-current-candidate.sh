#!/usr/bin/env bash
set -uo pipefail

ROOT="${ROOT:-/home/steve/llm-optimizations}"
DATA="${DATA:-$ROOT/data}"
PY="${PY:-/home/steve/.venvs/vllm-xpu/bin/python}"
TOKENIZER="${TOKENIZER:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
BASE="${BASE:-$DATA/qwen36-nospec-notrace-fixture-eager-tp2-20260617ao-candidate.json}"
TAG="${TAG:?TAG is required}"
PORT="${PORT:-18080}"

LOG="$DATA/$TAG.log"
SPEC="$DATA/$TAG-spec-trace.jsonl"
DRAFT="$DATA/$TAG-oracle-draft.jsonl"
CAND="$DATA/$TAG-candidate.json"
FIXTURE="$DATA/$TAG-fixture.json"
FIXTURE_MD="$DATA/$TAG-fixture.md"
SUMMARY="$DATA/$TAG-spec-summary.json"
GATE="$DATA/$TAG-gate-summary.json"
REPLAY="$DATA/$TAG-replay.json"
REPLAY_MD="$DATA/$TAG-replay.md"

rm -f "$LOG" "$SPEC" "$DRAFT" "$CAND" "$FIXTURE" "$FIXTURE_MD" \
  "$SUMMARY" "$GATE" "$REPLAY" "$REPLAY_MD"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  local pids
  pids=$(ps -eo pid,ppid,cmd \
    | rg "$PORT|VLLM::|vllm serve|launch-qwen36" \
    | rg -v 'rg ' \
    | awk '{print $1}' || true)
  if [[ -n "$pids" ]]; then
    kill -9 $pids 2>/dev/null || true
  fi
}
trap cleanup EXIT

ORACLE_TRACE="$BASE" \
NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-1}" \
TAG="$TAG" \
SPEC_TRACE_FILE="$SPEC" \
VLLM_XPU_ORACLE_DRAFT_LOG="$DRAFT" \
LOG_PATH="$LOG" \
PORT="$PORT" \
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-2}" \
XPU_DEVICE_LIST="${XPU_DEVICE_LIST:-0,1}" \
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.82}" \
ENABLE_XPU_GRAPH="${ENABLE_XPU_GRAPH:-0}" \
ENFORCE_EAGER="${ENFORCE_EAGER:-1}" \
COMPILE_CONFIG="${COMPILE_CONFIG:-$(printf '{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":%s}' "${MAX_CUDAGRAPH_CAPTURE_SIZE:-128}")}" \
VLLM_XPU_GDN_NATIVE_FALLBACK="${VLLM_XPU_GDN_NATIVE_FALLBACK:-decode,prefill}" \
DISABLE_FULL_ACCEPT_BONUS="${DISABLE_FULL_ACCEPT_BONUS:-1}" \
RECOMPUTE_SUPPRESSED_BONUS="${RECOMPUTE_SUPPRESSED_BONUS:-1}" \
VLLM_XPU_SPEC_DECODE_REPLACEMENT_MIN_MARGIN="${VLLM_XPU_SPEC_DECODE_REPLACEMENT_MIN_MARGIN:-999999}" \
VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT="${VLLM_XPU_SPEC_DECODE_RECOVER_SUPPRESSED_REPLACEMENT:-1}" \
VLLM_XPU_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT="${VLLM_XPU_SPEC_DECODE_NO_PREEMPT_SUPPRESSED_REPLACEMENT:-1}" \
"$ROOT/scripts/launch-qwen36-quark-int8-oracle-trace.sh" &
SERVER_PID=$!

ready=0
for _ in $(seq 1 240); do
  if curl -fsS "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "server exited before readiness; log follows" >&2
    tail -120 "$LOG" >&2 || true
    exit 1
  fi
  sleep 2
done

if [[ "$ready" != "1" ]]; then
  echo "server did not become ready; log follows" >&2
  tail -160 "$LOG" >&2 || true
  exit 1
fi

set +e
"$PY" "$ROOT/scripts/qwen36-completion-oracle-trace.py" \
  --base-url "http://127.0.0.1:$PORT" \
  --tokenizer "$TOKENIZER" \
  --prompt-tokens "${PROMPT_TOKENS:-512}" \
  --output-tokens "${OUTPUT_TOKENS:-32}" \
  --baseline-json "$BASE" \
  --case "${CASE_NAME:-natural_latency_plan}" \
  --request-id-prefix "$TAG" \
  --output-json "$CAND"
trace_rc=$?

SPEC_TRACE_JSONL="$SPEC" \
SPEC_SUMMARY_JSON="$SUMMARY" \
ACCEPTED_TRACE_JSON="$BASE" \
CANDIDATE_TRACE_JSON="$CAND" \
FIXTURE_JSON="$FIXTURE" \
FIXTURE_MD="$FIXTURE_MD" \
REPLAY_OUT_JSON="$REPLAY" \
REPLAY_OUT_MD="$REPLAY_MD" \
SUMMARY_JSON="$GATE" \
MODE=exact \
"$ROOT/scripts/run-qwen36-oracle-parity-gate.sh" "$TAG"
check_rc=$?

"$PY" - "$BASE" "$CAND" "$GATE" "$trace_rc" "$TAG" <<'PY'
import json
import sys
from pathlib import Path

base = json.load(open(sys.argv[1]))
cand = json.load(open(sys.argv[2]))
gate_path = Path(sys.argv[3])
gate = json.load(open(gate_path)) if gate_path.exists() else {}
b = base["cases"][0]["output_token_ids"]
c = cand["cases"][0]["output_token_ids"]
first = None
for i, (x, y) in enumerate(zip(b, c)):
    if x != y:
        first = i
        break
if first is None and len(b) != len(c):
    first = min(len(b), len(c))
print(json.dumps({
    "tag": sys.argv[5],
    "trace_rc": int(sys.argv[4]),
    "gate_pass": gate.get("pass"),
    "first_diff": first,
    "baseline_window": (
        b[max(0, first - 8):first + 12] if first is not None else []
    ),
    "candidate_window": (
        c[max(0, first - 8):first + 12] if first is not None else []
    ),
    "candidate_ids": c,
}, indent=2))
PY

exit "$check_rc"
