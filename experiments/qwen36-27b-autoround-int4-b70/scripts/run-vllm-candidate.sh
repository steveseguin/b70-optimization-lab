#!/usr/bin/env bash
set -euo pipefail

# Strict fresh-response candidate wrapper for Qwen3.6 27B vLLM/XPU lanes.
#
# This is intended for source/config/checkpoint screens that might become
# headline candidates. It starts one isolated TP1 server, runs the fixed Qwen
# realistic suite once per prompt with cached_tokens=0 required, optionally runs
# the deterministic Qwen text quality suite, then writes a compact summary.
#
# Diagnostic/synthetic runs should use separate scripts. LocalMaxxing
# submissions require this strict gate plus quality review.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
LABEL="${LABEL:-qwen27-candidate}"
GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19420}"
HOST="${HOST:-127.0.0.1}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-27b-candidate}"

RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates}"
RUN_DIR="${RUN_DIR:-$RUN_ROOT/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen36-27b-autoround-int4-b70-baselines}"
BENCH_OUT="${BENCH_OUT:-$OUT_DIR/${LABEL}-realistic128-chat-tokenids-qwensuite-${STAMP}.json}"
QUALITY_OUT="${QUALITY_OUT:-$OUT_DIR/quality-${LABEL}-repeat32-ctx1024-${STAMP}.json}"
SMOKE_OUT="${SMOKE_OUT:-$OUT_DIR/smoke-${LABEL}-${STAMP}.json}"
SUMMARY_OUT="${SUMMARY_OUT:-$OUT_DIR/${LABEL}-candidate-summary-${STAMP}.json}"
SUITE="${SUITE:-$ROOT/repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json}"
REQUEST_EXTRA_JSON="${REQUEST_EXTRA_JSON:-{\"chat_template_kwargs\":{\"enable_thinking\":false}}}"

MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
if [[ ! -e "$MODEL_DIR" ]]; then
  echo "MODEL_DIR does not exist: $MODEL_DIR" >&2
  exit 2
fi

export MODEL_DIR GPU_INDEX PORT HOST SERVED_MODEL_NAME
export QWEN36_27B_AR_VENV="${QWEN36_27B_AR_VENV:-/home/steve/.venvs/vllm-xpu}"
export HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
export QWEN36_27B_ENABLE_MTP="${QWEN36_27B_ENABLE_MTP:-1}"
export NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-3}"
export QWEN36_27B_ENABLE_XPU_GRAPH="${QWEN36_27B_ENABLE_XPU_GRAPH:-1}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
else
  export COMPILATION_CONFIG
fi
export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE="${VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE:-1}"
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE="${VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE:-0}"
export VLLM_XPU_LM_HEAD_INT8="${VLLM_XPU_LM_HEAD_INT8:-1}"
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE="${VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE:-bf16}"
export QWEN36_27B_DEFAULT_ENABLE_THINKING="${QWEN36_27B_DEFAULT_ENABLE_THINKING:-0}"
export QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS="${QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS:-1}"

PYTHON="${PYTHON:-$QWEN36_27B_AR_VENV/bin/python}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"
RUN_QUALITY="${RUN_QUALITY:-1}"
QUALITY_REPEAT_RUNS="${QUALITY_REPEAT_RUNS:-32}"
QUALITY_LONG_CONTEXT_TOKENS="${QUALITY_LONG_CONTEXT_TOKENS:-1024}"
QUALITY_SKIP_LONG_CONTEXT="${QUALITY_SKIP_LONG_CONTEXT:-0}"
QUALITY_BASELINE_JSON="${QUALITY_BASELINE_JSON:-}"

mkdir -p "$RUN_DIR" "$OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

{
  echo "date_utc=$STAMP"
  echo "label=$LABEL"
  echo "run_dir=$RUN_DIR"
  echo "model_dir=$MODEL_DIR"
  echo "served_model_name=$SERVED_MODEL_NAME"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "hf_home=$HF_HOME"
  echo "max_model_len=$MAX_MODEL_LEN"
  echo "max_num_batched_tokens=$MAX_NUM_BATCHED_TOKENS"
  echo "max_num_seqs=$MAX_NUM_SEQS"
  echo "gpu_memory_utilization=$GPU_MEMORY_UTILIZATION"
  echo "enable_mtp=$QWEN36_27B_ENABLE_MTP"
  echo "num_speculative_tokens=$NUM_SPECULATIVE_TOKENS"
  echo "enable_xpu_graph=$QWEN36_27B_ENABLE_XPU_GRAPH"
  echo "compilation_config=$COMPILATION_CONFIG"
  echo "promote_accepted_spec_state=$VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE"
  echo "nonspec_postprocess_accepted_state=$VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE"
  echo "gdn_packed_decode_with_source=${VLLM_XPU_GDN_PACKED_DECODE_WITH_SOURCE:-}"
  echo "lm_head_int8=$VLLM_XPU_LM_HEAD_INT8"
  echo "lm_head_int8_scale_dtype=$VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE"
  echo "mtp_text_input_ids_next=${VLLM_XPU_MTP_TEXT_INPUT_IDS_NEXT:-}"
  echo "mtp_next_dispatch_trace_file=${VLLM_XPU_MTP_NEXT_DISPATCH_TRACE_FILE:-}"
  echo "disable_compile_cache=${VLLM_DISABLE_COMPILE_CACHE:-}"
  echo "request_extra_json=$REQUEST_EXTRA_JSON"
  echo "qwen36_27b_speculative_config=${QWEN36_27B_SPECULATIVE_CONFIG:-}"
  echo "quality_repeat_runs=$QUALITY_REPEAT_RUNS"
  echo "quality_long_context_tokens=$QUALITY_LONG_CONTEXT_TOKENS"
  echo "quality_baseline_json=$QUALITY_BASELINE_JSON"
  echo "vllm_extra_args=${VLLM_EXTRA_ARGS:-}"
} > "$RUN_DIR/identity.env"

experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh \
  > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" \
  > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    break
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for http://127.0.0.1:${PORT}/v1/models" >&2
    break
  fi
  sleep 2
done

smoke_rc=99
bench_rc=99
quality_rc=0

if kill -0 "$server_pid" 2>/dev/null && [[ -s "$RUN_DIR/models.json" ]]; then
  set +e
  BASE_URL="http://127.0.0.1:${PORT}/v1" \
    MODEL="$SERVED_MODEL_NAME" \
    ENABLE_THINKING=0 \
    OUT="$SMOKE_OUT" \
    experiments/qwen36-27b-autoround-int4-b70/scripts/smoke-openai.sh \
    > "$RUN_DIR/smoke.stdout.log" 2>&1
  smoke_rc=$?

  "$PYTHON" scripts/bench-openai-realistic-suite.py \
    --base-url "http://127.0.0.1:${PORT}" \
    --model "$SERVED_MODEL_NAME" \
    --api-mode chat \
    --suite "$SUITE" \
    --max-tokens 512 \
    --metric-tokens 100 \
    --seed 1 \
    --request-extra-json "$REQUEST_EXTRA_JSON" \
    --return-token-ids \
    --out "$BENCH_OUT" \
    > "$RUN_DIR/bench.stdout.log" 2>&1
  bench_rc=$?

  if [[ "$RUN_QUALITY" != "0" ]]; then
    quality_args=(
      "$PYTHON" scripts/qwen36-text-quality-suite.py
      --base-url "http://127.0.0.1:${PORT}"
      --model "$SERVED_MODEL_NAME"
      --tokenizer "$MODEL_DIR"
      --repeat-runs "$QUALITY_REPEAT_RUNS"
      --long-context-tokens "$QUALITY_LONG_CONTEXT_TOKENS"
      --chat-template-kwargs-json '{"enable_thinking": false}'
      --output-json "$QUALITY_OUT"
    )
    if [[ "$QUALITY_SKIP_LONG_CONTEXT" != "0" ]]; then
      quality_args+=(--skip-long-context)
    fi
    if [[ -n "$QUALITY_BASELINE_JSON" ]]; then
      quality_args+=(--baseline-json "$QUALITY_BASELINE_JSON")
    fi
    "${quality_args[@]}" > "$RUN_DIR/quality.stdout.log" 2>&1
    quality_rc=$?
  fi
  set -e
fi

"$PYTHON" - "$SUMMARY_OUT" "$LABEL" "$RUN_DIR" "$MODEL_DIR" "$SMOKE_OUT" \
  "$BENCH_OUT" "$QUALITY_OUT" "$smoke_rc" "$bench_rc" "$quality_rc" <<'PY'
import json
import sys
from pathlib import Path

summary_out = Path(sys.argv[1])
label = sys.argv[2]
run_dir = Path(sys.argv[3])
model_dir = sys.argv[4]
smoke_path = Path(sys.argv[5])
bench_path = Path(sys.argv[6])
quality_path = Path(sys.argv[7])
smoke_rc = int(sys.argv[8])
bench_rc = int(sys.argv[9])
quality_rc = int(sys.argv[10])

def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"error": repr(exc), "path": str(path)}

smoke = read_json(smoke_path)
bench = read_json(bench_path)
quality = read_json(quality_path)
gate = (bench or {}).get("realistic_final_gate") or {}
fresh = (bench or {}).get("fresh_response_validity") or {}
bench_summary = (bench or {}).get("summary") or {}
speed = (bench_summary.get("tok_s_1_100_after_ttft") or {})
quality_pass = None
quality_baseline_match = None
if quality is not None:
    quality_pass = quality.get("pass_all")
    quality_baseline_match = quality.get("baseline_match_all")

status = {
    "smoke_rc": smoke_rc,
    "bench_rc": bench_rc,
    "quality_rc": quality_rc,
    "smoke_pass": (smoke or {}).get("pass"),
    "realistic_gate_passed": gate.get("passed"),
    "fresh_response_valid": fresh.get("valid"),
    "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    "quality_pass_all": quality_pass,
    "quality_baseline_match_all": quality_baseline_match,
}
out = {
    "classification": "strict_fresh_qwen27_candidate_summary",
    "label": label,
    "model_dir": model_dir,
    "run_dir": str(run_dir),
    "artifacts": {
        "identity": str(run_dir / "identity.env"),
        "server_log": str(run_dir / "server.stdout.log"),
        "models_json": str(run_dir / "models.json"),
        "smoke": str(smoke_path),
        "bench": str(bench_path),
        "quality": str(quality_path) if quality_path.exists() else None,
    },
    "status": status,
    "primary_metric": {
        "median_tok_s_1_100_after_ttft": speed.get("median"),
        "p10": speed.get("p10"),
        "mean": speed.get("mean"),
        "count": speed.get("count"),
    },
    "ttft_ms": (bench_summary.get("ttft_ms") or {}),
    "fresh_response_validity": fresh,
    "realistic_final_gate": gate,
    "quality_summary": (
        None if quality is None else {
            "pass_all": quality.get("pass_all"),
            "baseline_match_all": quality.get("baseline_match_all"),
            "exact": {item.get("name"): item.get("pass")
                      for item in quality.get("exact_cases", [])},
            "repeat_pass": (quality.get("repeat_case") or {}).get("pass"),
            "long_context_pass": (
                None if quality.get("long_context_case") is None
                else (quality.get("long_context_case") or {}).get("pass")
            ),
        }
    ),
}
summary_out.parent.mkdir(parents=True, exist_ok=True)
summary_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

cp "$SUMMARY_OUT" "$RUN_DIR/summary.json" 2>/dev/null || true

echo "$SUMMARY_OUT"
if [[ "$smoke_rc" -ne 0 || "$bench_rc" -ne 0 || "$quality_rc" -ne 0 ]]; then
  exit 1
fi
