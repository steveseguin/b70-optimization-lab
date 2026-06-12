#!/usr/bin/env bash
set -euo pipefail

# Bounded graph-path live-ABI route capture for Qwen3.6 Quark W8A8 INT8.
# This is diagnostic only: it records capture-safe/deferred MoE route evidence,
# converts clean route samples to route JSONL, optionally runs the route-class
# AOT planner, and restores the accepted endpoint afterward by default.

repo_dir="${REPO_DIR:-/home/steve/llm-optimizations}"
venv_python="${VENV_PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
tokenizer="${TOKENIZER:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
model="${MODEL:-qwen36-35b-a3b-fp8}"
base_url="${BASE_URL:-http://127.0.0.1:18080}"
tag="${TAG:-liveabi-graphcapture-20260612de}"
data_dir="${DATA_DIR:-$repo_dir/data}"
tmp_dir="${TMP_DIR:-/mnt/fast-ai/vllm-cache-exp/qwen36-${tag}}"
session="${TMUX_SESSION:-qwen36-tp4-${tag}}"
restore_session="${RESTORE_SESSION:-qwen36-tp4-accepted-restored-after-${tag}}"
log_path="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${tag}.log}"
accepted_restore_log="${ACCEPTED_RESTORE_LOG:-/tmp/qwen36-quark-int8-tp4-accepted-restored-after-${tag}.log}"
prompt_tokens="${PROMPT_TOKENS:-256}"
output_tokens="${OUTPUT_TOKENS:-48}"
repeats="${REPEATS:-2}"
layer_regex="${LIVE_ABI_LAYER_REGEX:-layers[.](9|19|29|39)[.]}"
rank="${LIVE_ABI_RANK:-0}"
max_lines="${LIVE_ABI_MAX_LINES:-800}"

mkdir -p "$data_dir" "$tmp_dir"

wait_health() {
  local url="$1"
  local attempts="${2:-120}"
  for _ in $(seq 1 "$attempts"); do
    local code
    code="$(curl -sS -m 2 -o /dev/null -w '%{http_code}' "$url/health" || true)"
    if [[ "$code" == "200" ]]; then
      return 0
    fi
    sleep 5
  done
  return 1
}

stop_session() {
  local name="$1"
  if tmux has-session -t "$name" 2>/dev/null; then
    tmux send-keys -t "$name" C-c || true
    sleep 8
  fi
}

cd "$repo_dir"

if curl -sS -m 2 -o /dev/null "$base_url/health"; then
  echo "Stopping currently running backend on $base_url"
  current_session="$(tmux ls 2>/dev/null | awk -F: '/qwen36-tp4-/ {print $1; exit}')"
  if [[ -n "${current_session:-}" ]]; then
    stop_session "$current_session"
  fi
fi

rm -f "$tmp_dir"/live-abi-*.jsonl

stop_session "$session"
stop_session "$restore_session"

echo "Starting graph live-ABI capture session $session"
tmux new-session -d -s "$session" \
  "cd '$repo_dir' && \
   TAG='$tag' \
   LOG_PATH='$log_path' \
   TORCHINDUCTOR_CACHE_DIR='$tmp_dir/torchinductor' \
   VLLM_CACHE_ROOT='$tmp_dir/vllm' \
   VLLM_XPU_MOE_LIVE_ABI_ALLOW=1 \
   VLLM_XPU_MOE_LIVE_ABI_FILE='$tmp_dir/live-abi-{rank}-{pid}.jsonl' \
   VLLM_XPU_MOE_LIVE_ABI_CAPTURE_SKIPS=1 \
   VLLM_XPU_MOE_LIVE_ABI_DEFER_CAPTURE_SAMPLES=1 \
   VLLM_XPU_MOE_LIVE_ABI_DEFER_CAPTURE_MAX_PENDING=8 \
   VLLM_XPU_MOE_LIVE_ABI_MAX_LINES='$max_lines' \
   VLLM_XPU_MOE_LIVE_ABI_LAYER_REGEX='$layer_regex' \
   VLLM_XPU_MOE_LIVE_ABI_RANK='$rank' \
   scripts/launch-qwen36-quark-int8-accepted.sh"

wait_health "$base_url" 180

metric_args=()
run_metric() {
  local label="$1"
  local preset="$2"
  local out_json="$data_dir/qwen36-quark-int8-tp4-${tag}-${label}.json"
  echo "Capturing prompt class $label"
  "$venv_python" scripts/measure-openai-endpoint-metrics.py \
    --base-url "$base_url" \
    --model "$model" \
    --tokenizer "$tokenizer" \
    --prompt-tokens "$prompt_tokens" \
    --output-tokens "$output_tokens" \
    --prompt-kind preset \
    --prompt-preset "$preset" \
    --repeats "$repeats" \
    --warmup-output-tokens 0 \
    --endpoint completions \
    --mode stream \
    --skip-vram \
    --out "$out_json"
  metric_args+=(--metrics "$label=$out_json")
}

run_metric natural-chat natural-chat
run_metric code code
run_metric structured structured
run_metric math-reasoning math-reasoning
run_metric repetitive repetitive

for live_abi_log in "$tmp_dir"/live-abi-*.jsonl; do
  if [[ -e "$live_abi_log" ]]; then
    cp "$live_abi_log" "$data_dir/qwen36-quark-int8-${tag}-$(basename "$live_abi_log")"
  fi
done

"$venv_python" scripts/qwen36-moe-live-abi-graph-capture-gate.py \
  "$tmp_dir"/live-abi-*.jsonl \
  --rank "$rank" \
  --require-capture-skip \
  --require-deferred-sample \
  --output-json "$data_dir/qwen36-quark-int8-liveabi-graph-capture-gate-${tag}.json" \
  --markdown-out "$data_dir/qwen36-quark-int8-liveabi-graph-capture-gate-${tag}.md"

"$venv_python" scripts/qwen36-live-abi-routes-to-jsonl.py \
  "$tmp_dir"/live-abi-*.jsonl \
  --drop-truncated \
  --drop-invalid-experts \
  --drop-duplicate-experts \
  --allow-empty \
  --output-jsonl "$data_dir/qwen36-quark-int8-liveabi-route-ledger-${tag}.jsonl" \
  --summary-json "$data_dir/qwen36-quark-int8-liveabi-route-ledger-${tag}.json" \
  --markdown-out "$data_dir/qwen36-quark-int8-liveabi-route-ledger-${tag}.md"

if [[ -s "$data_dir/qwen36-quark-int8-liveabi-route-ledger-${tag}.jsonl" ]]; then
  "$venv_python" scripts/qwen36-route-class-aot-plan.py \
    "$data_dir/qwen36-quark-int8-liveabi-route-ledger-${tag}.jsonl" \
    --output-json "$data_dir/qwen36-quark-int8-liveabi-route-class-aot-plan-${tag}.json" \
    --markdown-out "$data_dir/qwen36-quark-int8-liveabi-route-class-aot-plan-${tag}.md"
else
  cat > "$data_dir/qwen36-quark-int8-liveabi-route-class-aot-plan-${tag}.json" <<JSON
{
  "status": "skipped_no_clean_route_rows",
  "route_ledger": "data/qwen36-quark-int8-liveabi-route-ledger-${tag}.jsonl",
  "interpretation": "Graph-capture ABI evidence passed, but all deferred route samples were filtered as truncated, invalid, or duplicate/dummy rows. Do not promote route-class AOT conclusions from this run."
}
JSON
  cat > "$data_dir/qwen36-quark-int8-liveabi-route-class-aot-plan-${tag}.md" <<MD
# Qwen3.6 Route-Class AOT Plan

- Status: \`skipped_no_clean_route_rows\`.
- Route ledger: \`data/qwen36-quark-int8-liveabi-route-ledger-${tag}.jsonl\`.

Graph-capture ABI evidence passed, but all deferred route samples were filtered as truncated, invalid, or duplicate/dummy rows. Do not promote route-class AOT conclusions from this run.
MD
fi

if [[ "${RESTORE_ACCEPTED:-1}" == "1" ]]; then
  echo "Restoring accepted endpoint"
  stop_session "$session"
  tmux new-session -d -s "$restore_session" \
    "cd '$repo_dir' && LOG_PATH='$accepted_restore_log' scripts/launch-qwen36-quark-int8-accepted.sh"
  wait_health "$base_url" 180
fi

echo "done"
