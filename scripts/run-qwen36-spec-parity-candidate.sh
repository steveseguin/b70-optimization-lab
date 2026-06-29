#!/usr/bin/env bash
set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <label>" >&2
  echo "set SPEC_CONFIG to the speculative config JSON to test" >&2
  exit 2
fi

LABEL="$1"
ROOT="${ROOT:-/home/steve/llm-optimizations}"
DATA="${DATA:-$ROOT/data}"
PY="${PY:-/home/steve/.venvs/vllm-xpu/bin/python}"
TOKENIZER="${TOKENIZER:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
BASE="${BASE:-$DATA/qwen36-nospec-notrace-fixture-eager-tp2-20260617ao-candidate.json}"
PORT="${PORT:-18080}"
STAMP="${STAMP:-$(date -u +%Y%m%d%H%M%S)}"
TAG="${TAG:-$LABEL-$STAMP}"

LOG="$DATA/$TAG.log"
SPEC="$DATA/$TAG-spec-trace.jsonl"
CAND="$DATA/$TAG-candidate.json"
FIXTURE="$DATA/$TAG-fixture.json"
FIXTURE_MD="$DATA/$TAG-fixture.md"
SUMMARY="$DATA/$TAG-spec-summary.json"
GATE="$DATA/$TAG-gate-summary.json"
REPLAY="$DATA/$TAG-replay.json"
REPLAY_MD="$DATA/$TAG-replay.md"

mkdir -p "$DATA"
rm -f "$LOG" "$SPEC" "$CAND" "$FIXTURE" "$FIXTURE_MD" \
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

echo "[spec-parity:$LABEL] tag=$TAG"
echo "[spec-parity:$LABEL] base=$BASE"
echo "[spec-parity:$LABEL] spec_config=${SPEC_CONFIG:-<launcher-default>}"
echo "[spec-parity:$LABEL] log=$LOG"

TAG="$TAG" \
SPEC_TRACE_FILE="$SPEC" \
LOG_PATH="$LOG" \
PORT="$PORT" \
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-2}" \
XPU_DEVICE_LIST="${XPU_DEVICE_LIST:-0,1}" \
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.82}" \
ENABLE_XPU_GRAPH="${ENABLE_XPU_GRAPH:-0}" \
ENFORCE_EAGER="${ENFORCE_EAGER:-1}" \
COMPILE_CONFIG="${COMPILE_CONFIG:-$(printf '{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":%s}' "${MAX_CUDAGRAPH_CAPTURE_SIZE:-128}")}" \
"${SERVER_LAUNCHER:-$ROOT/scripts/launch-qwen36-quark-int8-ngram-trace.sh}" &
SERVER_PID=$!

ready=0
for _ in $(seq 1 "${READINESS_TIMEOUT_STEPS:-240}"); do
  if curl -fsS "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[spec-parity:$LABEL] server exited before readiness; log follows" >&2
    tail -120 "$LOG" >&2 || true
    exit 1
  fi
  sleep "${READINESS_SLEEP_S:-2}"
done

if [[ "$ready" != "1" ]]; then
  echo "[spec-parity:$LABEL] server did not become ready; log follows" >&2
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
MODE="${MODE:-exact}" \
EXPECT_SPEC_ACTIVE="${EXPECT_SPEC_ACTIVE:-1}" \
REQUIRE_SPEC_JOIN="${REQUIRE_SPEC_JOIN:-1}" \
MIN_DRAFT_TOKENS="${MIN_DRAFT_TOKENS:-1}" \
MIN_ACCEPTED_TOKENS="${MIN_ACCEPTED_TOKENS:-1}" \
MIN_ACCEPT_RATE_PCT="${MIN_ACCEPT_RATE_PCT:-}" \
ALLOW_REPLAY_ACCOUNTING_MISMATCH="${ALLOW_REPLAY_ACCOUNTING_MISMATCH:-0}" \
"$ROOT/scripts/run-qwen36-oracle-parity-gate.sh" "$TAG"
check_rc=$?

"$PY" - "$BASE" "$CAND" "$GATE" "$trace_rc" "$TAG" <<'PY'
import json
import sys
from pathlib import Path

base_path = Path(sys.argv[1])
cand_path = Path(sys.argv[2])
gate_path = Path(sys.argv[3])
base = json.load(open(base_path)) if base_path.exists() else {"cases": []}
cand = json.load(open(cand_path)) if cand_path.exists() else {"cases": []}
gate = json.load(open(gate_path)) if gate_path.exists() else {}

base_cases = {case.get("name"): case for case in base.get("cases", [])}
rows = []
for case in cand.get("cases", []):
    name = case.get("name")
    b = base_cases.get(name, {}).get("output_token_ids", [])
    c = case.get("output_token_ids", [])
    first = None
    for i, (x, y) in enumerate(zip(b, c)):
        if x != y:
            first = i
            break
    if first is None and len(b) != len(c):
        first = min(len(b), len(c))
    rows.append({
        "case": name,
        "first_diff": first,
        "baseline_window": b[max(0, (first or 0) - 8):(first or 0) + 12] if first is not None else [],
        "candidate_window": c[max(0, (first or 0) - 8):(first or 0) + 12] if first is not None else [],
        "candidate_count": len(c),
        "baseline_count": len(b),
    })

print(json.dumps({
    "tag": sys.argv[5],
    "trace_rc": int(sys.argv[4]),
    "gate_pass": gate.get("pass"),
    "gate_return_codes": gate.get("return_codes"),
    "cases": rows,
}, indent=2))
PY

exit "$check_rc"
