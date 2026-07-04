#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

GPU_INDEX="${GPU_INDEX:-1}"
PORT="${PORT:-19411}"
LABEL="${LABEL:-qwen27-webhie-int8lmhead-bf16scale-longctx}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUN_DIR:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/${LABEL}-${STAMP}}"
OUT_DIR="${OUT_DIR:-$ROOT/data/qwen36-27b-autoround-int4-b70-baselines}"
OUT="${OUT:-$OUT_DIR/${LABEL}-${STAMP}.json}"
SUITE="${SUITE:-$ROOT/repro/qwen36-27b-autoround-int4-b70/long-context-suite-v1.json}"
MAX_TARGET_PROMPT_TOKENS="${MAX_TARGET_PROMPT_TOKENS:-1024}"
LONG_MAX_TOKENS="${LONG_MAX_TOKENS:-128}"
LONG_REQUEST_EXTRA_JSON="${LONG_REQUEST_EXTRA_JSON:-{\"chat_template_kwargs\":{\"enable_thinking\":false}}}"
LONG_RETURN_TOKEN_IDS="${LONG_RETURN_TOKEN_IDS:-1}"
READINESS_TIMEOUT_S="${READINESS_TIMEOUT_S:-900}"

MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
export MODEL_DIR GPU_INDEX PORT
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
export VLLM_XPU_LM_HEAD_INT8="${VLLM_XPU_LM_HEAD_INT8:-1}"
export VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE="${VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE:-bf16}"
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
  echo "suite=$SUITE"
  echo "max_target_prompt_tokens=$MAX_TARGET_PROMPT_TOKENS"
  echo "long_max_tokens=$LONG_MAX_TOKENS"
  echo "long_request_extra_json=$LONG_REQUEST_EXTRA_JSON"
  echo "long_return_token_ids=$LONG_RETURN_TOKEN_IDS"
  echo "model_dir=$MODEL_DIR"
  echo "max_model_len=$MAX_MODEL_LEN"
  echo "max_num_batched_tokens=$MAX_NUM_BATCHED_TOKENS"
  echo "max_num_seqs=$MAX_NUM_SEQS"
  echo "gpu_memory_utilization=$GPU_MEMORY_UTILIZATION"
  echo "enable_mtp=$QWEN36_27B_ENABLE_MTP"
  echo "num_speculative_tokens=$NUM_SPECULATIVE_TOKENS"
  echo "enable_xpu_graph=$QWEN36_27B_ENABLE_XPU_GRAPH"
  echo "compilation_config=$COMPILATION_CONFIG"
  echo "lm_head_int8=$VLLM_XPU_LM_HEAD_INT8"
  echo "lm_head_int8_scale_dtype=$VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE"
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

bench_args=(
  python3 scripts/bench-openai-long-context-suite.py
  --base-url "http://127.0.0.1:${PORT}"
  --model "${SERVED_MODEL_NAME:-qwen36-27b-int4-autoround}"
  --suite "$SUITE"
  --max-target-prompt-tokens "$MAX_TARGET_PROMPT_TOKENS"
  --max-tokens "$LONG_MAX_TOKENS"
  --request-extra-json "$LONG_REQUEST_EXTRA_JSON"
  --out "$OUT"
)
if [[ "$LONG_RETURN_TOKEN_IDS" != "0" ]]; then
  bench_args+=(--return-token-ids)
fi
"${bench_args[@]}" > "$RUN_DIR/bench.stdout.log" 2>&1

cp "$OUT" "$RUN_DIR/result.json"
python3 - "$OUT" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path) as f:
    result = json.load(f)
summary = result.get("summary", {})
print(json.dumps({
    "path": path,
    "long_context_gate": summary.get("long_context_gate", {}).get("passed"),
    "cached_tokens_all_zero": summary.get("cached_tokens_all_zero"),
    "quality_pass_all": summary.get("quality_pass_all"),
    "prompt_tokens": summary.get("prompt_tokens"),
    "ttft_s": summary.get("ttft_s"),
    "prefill_tok_s_approx": summary.get("prefill_tok_s_approx"),
    "tok_s_after_ttft": summary.get("tok_s_after_ttft"),
    "tok_s_wall": summary.get("tok_s_wall"),
}, indent=2))
PY
echo "$OUT"
