#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-wide-topk-reranker-4gpu-${STAMP}}"
CORPUS="${CORPUS:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z}"
TARGET_MODEL="${TARGET_MODEL:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
DRAFT="${DRAFT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z/all-r5-lr3e-6-decay0p25/checkpoint}"
PY="${PY:-/home/steve/.venvs/vllm-xpu/bin/python}"
BATCH_SIZE="${BATCH_SIZE:-16}"
EPOCHS="${EPOCHS:-3}"
MAX_TRAIN_ROWS="${MAX_TRAIN_ROWS:-0}"
MAX_HELDOUT_STARTS="${MAX_HELDOUT_STARTS:-0}"
EVAL_EVERY="${EVAL_EVERY:-500}"
DTYPE="${DTYPE:-bfloat16}"

mkdir -p "$RUN_ROOT"

run_variant() {
  local gpu="$1"
  local label="$2"
  local topk="$3"
  local hidden="$4"
  local lr="$5"
  local out="$RUN_ROOT/$label"
  mkdir -p "$out"
  (
    set -euo pipefail
    cd "$repo_dir"
    unset ONEAPI_DEVICE_SELECTOR
    export ZE_AFFINITY_MASK="$gpu"
    "$PY" scripts/train-qwen27-eagle3-topk-reranker.py \
      --dataset-dir "$CORPUS/shard-0/dataset" \
      --dataset-dir "$CORPUS/shard-1/dataset" \
      --dataset-dir "$CORPUS/shard-2/dataset" \
      --heldout-dir "$CORPUS/shard-3/dataset" \
      --draft-dir "$DRAFT" \
      --target-model "$TARGET_MODEL" \
      --out-dir "$out" \
      --topk "$topk" \
      --reranker-type mlp \
      --reranker-hidden "$hidden" \
      --rollout-steps 5 \
      --epochs "$EPOCHS" \
      --batch-size "$BATCH_SIZE" \
      --lr "$lr" \
      --max-train-rows "$MAX_TRAIN_ROWS" \
      --max-heldout-starts "$MAX_HELDOUT_STARTS" \
      --eval-every "$EVAL_EVERY" \
      --dtype "$DTYPE" \
      --device xpu:0 \
      > "$out/stdout.log" 2>&1
  )
}

variants=(
  "0|k64-h512-lr1e-3|64|512|1e-3"
  "1|k64-h1024-lr5e-4|64|1024|5e-4"
  "2|k128-h512-lr5e-4|128|512|5e-4"
  "3|k128-h1024-lr3e-4|128|1024|3e-4"
)

pids=()
for item in "${variants[@]}"; do
  IFS='|' read -r gpu label topk hidden lr <<< "$item"
  echo "launch label=$label gpu=$gpu topk=$topk hidden=$hidden lr=$lr draft=$DRAFT"
  run_variant "$gpu" "$label" "$topk" "$hidden" "$lr" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

exit "$rc"
