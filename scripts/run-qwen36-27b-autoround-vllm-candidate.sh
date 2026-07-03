#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GPU_INDEX="${GPU_INDEX:-1}"
PORT="${PORT:-19411}"
LABEL="${LABEL:-intel-mtp3-xpugraph1-cg8-candidate-realistic128-chat-tokenids-qwensuite}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen36-27b-autoround-int4-b70-baselines}"
OUT="${OUT:-$OUT_DIR/${LABEL}-${STAMP}.json}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-600}"

export GPU_INDEX PORT
export MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
export MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-1024}"
export MAX_NUM_SEQS="${MAX_NUM_SEQS:-1}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.95}"
export QWEN36_27B_ENABLE_MTP="${QWEN36_27B_ENABLE_MTP:-1}"
export NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-3}"
export QWEN36_27B_ENABLE_XPU_GRAPH="${QWEN36_27B_ENABLE_XPU_GRAPH:-1}"
export COMPILATION_CONFIG="${COMPILATION_CONFIG:-{\"cudagraph_mode\":\"PIECEWISE\",\"max_cudagraph_capture_size\":8}}"
export VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE="${VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE:-1}"
export VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE="${VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE:-0}"
export QWEN36_27B_DEFAULT_ENABLE_THINKING="${QWEN36_27B_DEFAULT_ENABLE_THINKING:-0}"
export QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS="${QWEN36_27B_ENABLE_PROMPT_TOKEN_DETAILS:-1}"

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
  echo "max_model_len=$MAX_MODEL_LEN"
  echo "max_num_batched_tokens=$MAX_NUM_BATCHED_TOKENS"
  echo "max_num_seqs=$MAX_NUM_SEQS"
  echo "gpu_memory_utilization=$GPU_MEMORY_UTILIZATION"
  echo "enable_mtp=$QWEN36_27B_ENABLE_MTP"
  echo "num_speculative_tokens=$NUM_SPECULATIVE_TOKENS"
  echo "enable_xpu_graph=$QWEN36_27B_ENABLE_XPU_GRAPH"
  echo "compilation_config=$COMPILATION_CONFIG"
  echo "reasoning_parser=${QWEN36_27B_REASONING_PARSER-qwen3}"
  echo "promote_accepted_spec_state=$VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE"
  echo "nonspec_postprocess_accepted_state=$VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE"
  echo "vllm_extra_args=${VLLM_EXTRA_ARGS:-}"
} > "$RUN_DIR/identity.env"

experiments/qwen36-27b-autoround-int4-b70/scripts/serve-vllm.sh \
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

python3 scripts/bench-openai-realistic-suite.py \
  --base-url "http://127.0.0.1:${PORT}" \
  --model "${SERVED_MODEL_NAME:-qwen36-27b-int4-autoround}" \
  --api-mode chat \
  --suite repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json \
  --max-tokens 128 \
  --metric-tokens 100 \
  --return-token-ids \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
  --out "$OUT" \
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
