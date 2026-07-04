#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${MODEL_DIR:?MODEL_DIR must be a HF repo id or local model path}"
GPU_INDEX="${GPU_INDEX:-0}"
PORT="${PORT:-19700}"
HOST="${HOST:-127.0.0.1}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-rapid-vllm-xpu-model}"
LABEL="${LABEL:-${SERVED_MODEL_NAME}-realistic}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/rapid-model-snapshots-b70/vllm-runs}"
RUN_DIR="${RUN_DIR:-$RUN_ROOT/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/rapid-model-snapshots-b70}"
BENCH_OUT="${BENCH_OUT:-$OUT_DIR/${LABEL}-${STAMP}.json}"
SUMMARY_OUT="${SUMMARY_OUT:-$OUT_DIR/${LABEL}-summary-${STAMP}.json}"
SUITE="${SUITE:-$ROOT/repro/rapid-model-snapshots-b70/realistic-suite-v1.json}"
MAX_TOKENS="${MAX_TOKENS:-128}"
METRIC_TOKENS="${METRIC_TOKENS:-100}"
REQUEST_EXTRA_JSON="${REQUEST_EXTRA_JSON:-{}}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-1200}"
VLLM_VENV="${VLLM_VENV:-/home/steve/.venvs/vllm-xpu}"

mkdir -p "$RUN_DIR" "$OUT_DIR"

server_pid=""
cleanup() {
  if [[ -n "${server_pid:-}" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT"

{
  echo "date_utc=$STAMP"
  echo "label=$LABEL"
  echo "model_dir=$MODEL_DIR"
  echo "served_model_name=$SERVED_MODEL_NAME"
  echo "gpu_index=$GPU_INDEX"
  echo "port=$PORT"
  echo "run_dir=$RUN_DIR"
  echo "bench_out=$BENCH_OUT"
  echo "suite=$SUITE"
  echo "max_tokens=$MAX_TOKENS"
  echo "metric_tokens=$METRIC_TOKENS"
  echo "request_extra_json=$REQUEST_EXTRA_JSON"
  echo "hf_home=${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
  echo "max_model_len=${MAX_MODEL_LEN:-4096}"
  echo "max_num_batched_tokens=${MAX_NUM_BATCHED_TOKENS:-2048}"
  echo "max_num_seqs=${MAX_NUM_SEQS:-1}"
  echo "gpu_memory_utilization=${GPU_MEMORY_UTILIZATION:-0.95}"
  echo "tensor_parallel_size=${TENSOR_PARALLEL_SIZE:-1}"
  echo "enable_prefix_caching=${ENABLE_PREFIX_CACHING:-0}"
  echo "enable_xpu_graph=${ENABLE_XPU_GRAPH:-0}"
  echo "compilation_config=${COMPILATION_CONFIG:-}"
  echo "speculative_config=${SPECULATIVE_CONFIG:-}"
  echo "vllm_extra_args=${VLLM_EXTRA_ARGS:-}"
} > "$RUN_DIR/identity.env"

MODEL_DIR="$MODEL_DIR" GPU_INDEX="$GPU_INDEX" PORT="$PORT" HOST="$HOST" \
SERVED_MODEL_NAME="$SERVED_MODEL_NAME" VLLM_VENV="$VLLM_VENV" \
  scripts/serve-rapid-vllm-xpu-model.sh \
  > "$RUN_DIR/server.stdout.log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$RUN_DIR/server.pid"

deadline=$((SECONDS + READINESS_TIMEOUT_S))
until curl -fsS "http://127.0.0.1:${PORT}/v1/models" > "$RUN_DIR/models.json" 2> "$RUN_DIR/models.err"; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "server exited before readiness; see $RUN_DIR/server.stdout.log" >&2
    tail -120 "$RUN_DIR/server.stdout.log" >&2 || true
    exit 1
  fi
  if (( SECONDS >= deadline )); then
    echo "timed out waiting for http://127.0.0.1:${PORT}/v1/models" >&2
    tail -120 "$RUN_DIR/server.stdout.log" >&2 || true
    exit 1
  fi
  sleep 2
done

"$VLLM_VENV/bin/python" scripts/bench-openai-realistic-suite.py \
  --base-url "http://127.0.0.1:${PORT}" \
  --model "$SERVED_MODEL_NAME" \
  --api-mode chat \
  --suite "$SUITE" \
  --max-tokens "$MAX_TOKENS" \
  --metric-tokens "$METRIC_TOKENS" \
  --request-extra-json "$REQUEST_EXTRA_JSON" \
  --return-token-ids \
  --out "$BENCH_OUT" \
  > "$RUN_DIR/bench.stdout.log" 2>&1

cp "$BENCH_OUT" "$RUN_DIR/result.json"

"$VLLM_VENV/bin/python" - "$SUMMARY_OUT" "$LABEL" "$RUN_DIR" "$MODEL_DIR" "$BENCH_OUT" <<'PY'
import json
import sys
from pathlib import Path

summary_out = Path(sys.argv[1])
label = sys.argv[2]
run_dir = Path(sys.argv[3])
model_dir = sys.argv[4]
bench_path = Path(sys.argv[5])
bench = json.loads(bench_path.read_text())
gate = bench.get("realistic_final_gate") or {}
fresh = bench.get("fresh_response_validity") or {}
summary = bench.get("summary") or {}
primary = summary.get("tok_s_1_100_after_ttft") or {}
full = summary.get("tok_s_after_ttft_full") or {}
wall = summary.get("tok_s_wall_full") or {}
ttft = summary.get("ttft_ms") or {}

out = {
    "classification": "strict_fresh_rapid_vllm_candidate_summary",
    "label": label,
    "model_dir": model_dir,
    "run_dir": str(run_dir),
    "artifacts": {
        "identity": str(run_dir / "identity.env"),
        "server_log": str(run_dir / "server.stdout.log"),
        "models_json": str(run_dir / "models.json"),
        "bench": str(bench_path),
    },
    "status": {
        "realistic_gate_passed": gate.get("passed"),
        "fresh_response_valid": fresh.get("valid"),
        "cached_tokens_all_zero": gate.get("cached_tokens_all_zero"),
    },
    "primary_metric": {
        "median_tok_s_1_100_after_ttft": primary.get("median"),
        "p10": primary.get("p10"),
        "mean": primary.get("mean"),
        "count": primary.get("count"),
    },
    "secondary_metrics": {
        "median_tok_s_after_ttft_full": full.get("median"),
        "median_wall_tok_s_full": wall.get("median"),
        "median_ttft_ms": ttft.get("median"),
    },
    "fresh_response_validity": fresh,
    "realistic_final_gate": gate,
}
summary_out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

cp "$SUMMARY_OUT" "$RUN_DIR/summary.json"
echo "$SUMMARY_OUT"
