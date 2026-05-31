#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/configs/deepseek-v4-flash-autoround.env"

MODEL="${MODEL:-$DEEPSEEK_V4_AR_MODEL_DIR}"
VENV="${VENV:-$DEEPSEEK_V4_AR_VENV}"
OUTDIR="${OUTDIR:-$DEEPSEEK_V4_AR_OUTDIR}"
RUN_TIMEOUT="${RUN_TIMEOUT:-}"
RUN_TIMEOUT_KILL_AFTER="${RUN_TIMEOUT_KILL_AFTER:-30s}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

if [ -n "$GPU_MEMORY_UTILIZATION" ]; then
  EXTRA_ARGS="$EXTRA_ARGS --gpu-memory-utilization $GPU_MEMORY_UTILIZATION"
fi
if [ -n "$KV_CACHE_DTYPE" ]; then
  EXTRA_ARGS="$EXTRA_ARGS --kv-cache-dtype $KV_CACHE_DTYPE"
fi
if [ -n "$DEEPSEEK_V4_MOE_BACKEND" ]; then
  EXTRA_ARGS="$EXTRA_ARGS --kernel-config {\"moe_backend\":\"$DEEPSEEK_V4_MOE_BACKEND\"}"
fi

if [ ! -d "$VENV" ]; then
  echo "Missing venv: $VENV" >&2
  exit 1
fi
if [ ! -d "$MODEL" ]; then
  echo "Model directory is missing: $MODEL" >&2
  echo "Run: bash $ROOT/scripts/download-model.sh" >&2
  exit 1
fi

mkdir -p "$OUTDIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
tag="tp${TP}-p${INPUT_LEN}n${OUTPUT_LEN}-${ts}"
log="$OUTDIR/vllm-deepseek-v4-flash-autoround-${tag}.log"
json="$OUTDIR/vllm-deepseek-v4-flash-autoround-${tag}.json"
runtime_json="$OUTDIR/vllm-deepseek-v4-flash-autoround-${tag}.runtime.json"

source "$VENV/bin/activate"
if [ -f /opt/intel/oneapi/compiler/2025.3/env/vars.sh ]; then
  source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1
fi

export LD_LIBRARY_PATH="$VENV/lib:$VENV/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"

runner=(/usr/bin/time -v)
if [ -n "$RUN_TIMEOUT" ]; then
  runner=(timeout --foreground --signal=TERM --kill-after="$RUN_TIMEOUT_KILL_AFTER" "$RUN_TIMEOUT" /usr/bin/time -v)
fi

{
  echo "log=$log"
  echo "json=$json"
  echo "runtime_json=$runtime_json"
  echo "model=$MODEL"
  echo "root=$ROOT"
  echo "repo=$DEEPSEEK_V4_AR_REPO"
  echo "revision=$DEEPSEEK_V4_AR_REVISION"
  echo "tp=$TP"
  echo "dtype=$DTYPE"
  echo "kv_cache_dtype=$KV_CACHE_DTYPE"
  echo "max_model_len=$MAX_MODEL_LEN"
  echo "max_batched_tokens=$MAX_BATCHED_TOKENS"
  echo "max_num_seqs=$MAX_NUM_SEQS"
  echo "input_len=$INPUT_LEN"
  echo "output_len=$OUTPUT_LEN"
  echo "num_prompts=$NUM_PROMPTS"
  echo "oneapi_device_selector=${ONEAPI_DEVICE_SELECTOR:-}"
  echo "ze_affinity_mask=${ZE_AFFINITY_MASK:-}"
  echo "ccl_atl_transport=${CCL_ATL_TRANSPORT:-}"
  echo "ccl_ze_ipc_exchange=${CCL_ZE_IPC_EXCHANGE:-}"
  echo "ccl_topo_p2p_access=${CCL_TOPO_P2P_ACCESS:-}"
  echo "extra_args=$EXTRA_ARGS"
  echo "start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  if [ -x /home/steve/llm-optimizations-publish/scripts/inspect-vllm-runtime.py ]; then
    python /home/steve/llm-optimizations-publish/scripts/inspect-vllm-runtime.py \
      --output "$runtime_json" || true
    if [ -s "$runtime_json" ]; then
      jq -c . "$runtime_json" || true
    fi
  fi

  "${runner[@]}" vllm bench throughput \
    --backend vllm \
    --model "$MODEL" \
    --tokenizer "$MODEL" \
    --trust-remote-code \
    --dtype "$DTYPE" \
    --tensor-parallel-size "$TP" \
    --distributed-executor-backend mp \
    --max-model-len "$MAX_MODEL_LEN" \
    --max-num-batched-tokens "$MAX_BATCHED_TOKENS" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --dataset-name random \
    --random-input-len "$INPUT_LEN" \
    --random-output-len "$OUTPUT_LEN" \
    --random-range-ratio 0 \
    --num-prompts "$NUM_PROMPTS" \
    --disable-log-stats \
    --output-json "$json" \
    $EXTRA_ARGS

  echo "end=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$log" 2>&1

printf 'log=%s\njson=%s\n' "$log" "$json"
if [ -s "$json" ]; then
  jq -c . "$json"
else
  tail -120 "$log"
fi
