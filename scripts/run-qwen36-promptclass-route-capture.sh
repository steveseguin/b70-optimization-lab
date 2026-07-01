#!/usr/bin/env bash
set -euo pipefail

# Reproducible bounded route-capture sweep for prompt-class MoE locality.
# This intentionally runs the route-capture launcher, which disables graph
# capture and should not be used for speed claims.

repo_dir="${REPO_DIR:-/home/steve/llm-optimizations}"
venv_python="${VENV_PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
tokenizer="${TOKENIZER:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
model="${MODEL:-qwen36-35b-a3b-fp8}"
base_url="${BASE_URL:-http://127.0.0.1:18080}"
tag="${TAG:-promptclass-routecapture-20260611}"
data_dir="${DATA_DIR:-$repo_dir/data}"
tmp_dir="${TMP_DIR:-/tmp/qwen36-${tag}}"
session="${TMUX_SESSION:-qwen36-tp4-${tag}}"
log_path="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${tag}.log}"
prompt_tokens="${PROMPT_TOKENS:-256}"
output_tokens="${OUTPUT_TOKENS:-64}"
long_prompt_tokens="${LONG_PROMPT_TOKENS:-4096}"
long_output_tokens="${LONG_OUTPUT_TOKENS:-32}"
seed="${SEED:-20260611}"

mkdir -p "$data_dir" "$tmp_dir"

wait_health() {
  local url="$1"
  local attempts="${2:-90}"
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
    sleep 6
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

rm -f "$tmp_dir"/routes-*.jsonl

echo "Starting route-capture session $session"
tmux new-session -d -s "$session" \
  "cd '$repo_dir' && TAG='$tag' CAPTURE_FILE='$tmp_dir/routes-{pid}.jsonl' CAPTURE_STAGE_REGEX='^quark_int8_apply$' CAPTURE_LAYER_REGEX='layers\\.(8|9|14|20|21)\\.' CAPTURE_MIN_NUM_TOKENS=1 CAPTURE_MAX_NUM_TOKENS=1 CAPTURE_MAX_LINES=0 CAPTURE_INCLUDE_IDS=0 LOG_PATH='$log_path' scripts/launch-qwen36-quark-int8-route-capture.sh"

wait_health "$base_url" 120

metric_args=()
run_metric() {
  local label="$1"
  local preset="$2"
  local in_tokens="$3"
  local out_tokens="$4"
  local out_json="$data_dir/qwen36-quark-int8-tp4-${tag}-${label}.json"
  echo "Capturing prompt class $label"
  "$venv_python" scripts/measure-openai-endpoint-metrics.py \
    --base-url "$base_url" \
    --model "$model" \
    --tokenizer "$tokenizer" \
    --prompt-tokens "$in_tokens" \
    --output-tokens "$out_tokens" \
    --prompt-kind preset \
    --prompt-preset "$preset" \
    --repeats 1 \
    --warmup-output-tokens 0 \
    --endpoint completions \
    --mode stream \
    --skip-vram \
    --out "$out_json"
  metric_args+=(--metrics "$label=$out_json")
}

run_metric natural-chat natural-chat "$prompt_tokens" "$output_tokens"
run_metric code code "$prompt_tokens" "$output_tokens"
run_metric structured structured "$prompt_tokens" "$output_tokens"
run_metric math-reasoning math-reasoning "$prompt_tokens" "$output_tokens"
run_metric repetitive repetitive "$prompt_tokens" "$output_tokens"
run_metric long-natural natural-chat "$long_prompt_tokens" "$long_output_tokens"

for route_file in "$tmp_dir"/routes-*.jsonl; do
  cp "$route_file" "$data_dir/qwen36-quark-int8-tp4-${tag}-$(basename "$route_file")"
done

"$venv_python" scripts/filter-qwen36-route-jsonl-by-metric-windows.py \
  --routes "$data_dir/qwen36-quark-int8-tp4-${tag}-routes-*.jsonl" \
  "${metric_args[@]}" \
  --out-dir "$data_dir" \
  --prefix "qwen36-quark-int8-tp4-${tag}-routes" \
  --summary-json "$data_dir/qwen36-quark-int8-tp4-${tag}-route-window-summary.json"

heatmap_args=()
for label in natural-chat code structured math-reasoning repetitive long-natural; do
  heatmap_args+=(--input "$label=$data_dir/qwen36-quark-int8-tp4-${tag}-routes-${label}.jsonl")
done

"$venv_python" scripts/analyze-qwen36-moe-route-heatmap.py \
  "${heatmap_args[@]}" \
  --topn 16 \
  --max-num-tokens 1 \
  --out "$data_dir/qwen36-quark-int8-tp4-${tag}-heatmap.json" \
  --limit 30

if [[ "${RESTORE_ACCEPTED:-1}" == "1" ]]; then
  echo "Restoring accepted endpoint"
  stop_session "$session"
  tmux new-session -d -s "qwen36-tp4-accepted-restored-after-${tag}" \
    "cd '$repo_dir' && LOG_PATH='/tmp/qwen36-quark-int8-tp4-accepted-restored-after-${tag}.log' scripts/launch-qwen36-quark-int8-accepted.sh"
  wait_health "$base_url" 120
fi

echo "done"
