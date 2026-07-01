#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <tag> <comma-separated-layer-list>" >&2
  exit 2
fi

TAG="$1"
LAYERS="$2"
DATA="${DATA:-/home/steve/llm-optimizations/data}"
PORT="${PORT:-18183}"
BASELINE_JSON="${BASELINE_JSON:-$DATA/qwen36-nospec-current-eager-tp2-20260617i-candidate.json}"

old=$(ps -eo pid,ppid,cmd | rg "${PORT}|VLLM::|vllm serve" | rg -v 'rg ' | awk '{print $1}' || true)
if [[ -n "${old}" ]]; then
  # Diagnostic helper owns this port; do not leave stale workers around.
  kill -9 ${old} || true
fi

rm -f \
  "$DATA/${TAG}.log" \
  "$DATA/${TAG}-candidate.json" \
  "$DATA/${TAG}-gdnrow-r0.jsonl" \
  "$DATA/${TAG}-model-input-r0.jsonl"

export PORT
export LOG_PATH="$DATA/${TAG}.log"
export TP_SIZE="${TP_SIZE:-2}"
export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0,1}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0,1}"
export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.82}"
export COMPILATION_CONFIG="${COMPILATION_CONFIG:-{\"cudagraph_mode\":\"PIECEWISE\",\"max_cudagraph_capture_size\":128}}"
export VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:---enforce-eager --no-async-scheduling}"
export VLLM_XPU_INT8_MOE_MIXED_WORKSPACE="${VLLM_XPU_INT8_MOE_MIXED_WORKSPACE:-1}"
export VLLM_XPU_HOLD_SPEC_DECODE_WHEN_WAITING="${VLLM_XPU_HOLD_SPEC_DECODE_WHEN_WAITING:-1}"
export VLLM_XPU_GDN_NATIVE_FALLBACK="${VLLM_XPU_GDN_NATIVE_FALLBACK:-decode,prefill}"
export VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK="${VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK:-1}"
export VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY="${VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY:-1}"

export MODEL_INPUT_TRACE_FILE="$DATA/${TAG}-model-input-r0.jsonl"
export MODEL_INPUT_TRACE_MAX_LINES="${MODEL_INPUT_TRACE_MAX_LINES:-2000}"
export MODEL_INPUT_TRACE_RANK="${MODEL_INPUT_TRACE_RANK:-0}"

export VLLM_XPU_GDN_ROW_TRACE_FILE="$DATA/${TAG}-gdnrow-r0.jsonl"
export VLLM_XPU_GDN_ROW_TRACE_MAX_LINES="${VLLM_XPU_GDN_ROW_TRACE_MAX_LINES:-2400}"
export VLLM_XPU_GDN_ROW_TRACE_RANK="${VLLM_XPU_GDN_ROW_TRACE_RANK:-0}"
export VLLM_XPU_GDN_ROW_TRACE_LAYERS="$LAYERS"
export VLLM_XPU_GDN_ROW_TRACE_STAGES="${VLLM_XPU_GDN_ROW_TRACE_STAGES:-forward_post_core}"
export VLLM_XPU_GDN_ROW_TRACE_STATE_ONLY="${VLLM_XPU_GDN_ROW_TRACE_STATE_ONLY:-1}"
export VLLM_XPU_GDN_ROW_TRACE_ROW_LIMIT="${VLLM_XPU_GDN_ROW_TRACE_ROW_LIMIT:-1}"
export VLLM_XPU_GDN_ROW_TRACE_HEAD="${VLLM_XPU_GDN_ROW_TRACE_HEAD:-4}"
export VLLM_XPU_GDN_ROW_TRACE_STATE_LIMIT="${VLLM_XPU_GDN_ROW_TRACE_STATE_LIMIT:-2}"
export VLLM_XPU_GDN_ROW_TRACE_STATE_HEAD="${VLLM_XPU_GDN_ROW_TRACE_STATE_HEAD:-4}"

/home/steve/llm-optimizations/scripts/launch-qwen36-quark-int8-accepted.sh &
server_pid=$!
trap 'kill -9 "$server_pid" 2>/dev/null || true; pkill -9 -P "$server_pid" 2>/dev/null || true' EXIT

ready=0
for _ in $(seq 1 180); do
  if curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/tmp/${TAG}-models.json 2>/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "server exited early; tail follows" >&2
    tail -n 120 "$DATA/${TAG}.log" >&2 || true
    exit 1
  fi
  sleep 1
done

if [[ "$ready" != 1 ]]; then
  echo "server did not become ready; tail follows" >&2
  tail -n 160 "$DATA/${TAG}.log" >&2 || true
  exit 1
fi

/home/steve/.venvs/vllm-xpu/bin/python \
  /home/steve/llm-optimizations/scripts/qwen36-completion-oracle-trace.py \
  --base-url "http://127.0.0.1:${PORT}" \
  --model qwen36-35b-a3b-fp8 \
  --prompt-tokens 512 \
  --output-tokens 32 \
  --seed 20260611 \
  --case natural_latency_plan \
  --baseline-json "$BASELINE_JSON" \
  --request-id-prefix "$TAG" \
  --output-json "$DATA/${TAG}-candidate.json"

python3 - "$DATA/${TAG}-candidate.json" "$DATA/${TAG}-gdnrow-r0.jsonl" <<'PY'
import collections
import json
import sys

candidate_path, trace_path = sys.argv[1:3]
candidate = json.load(open(candidate_path))
layers = collections.Counter()
rows = 0
with open(trace_path) as handle:
    for line in handle:
        row = json.loads(line)
        rows += 1
        layers[row.get("layer_idx")] += 1
print(json.dumps({
    "candidate": candidate_path,
    "baseline_match_all": candidate.get("baseline_match_all"),
    "comparison": candidate.get("baseline_comparisons"),
    "trace_rows": rows,
    "trace_layers": sorted(layers.items()),
}, indent=2, sort_keys=True))
PY
