#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-rankpush-4gpu-${STAMP}}"
CORPUS="${CORPUS:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z}"
TARGET_MODEL="${TARGET_MODEL:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
START_DRAFT="${START_DRAFT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-v6b-allscope-20260707T075425Z/all-r5-lr3e-6-decay0p25/checkpoint}"
PY="${PY:-/home/steve/.venvs/vllm-xpu/bin/python}"
BATCH_SIZE="${BATCH_SIZE:-64}"
EPOCHS="${EPOCHS:-4}"
MAX_TRAIN_ROWS="${MAX_TRAIN_ROWS:-0}"
MAX_HELDOUT_ROWS="${MAX_HELDOUT_ROWS:-0}"
EVAL_EVERY="${EVAL_EVERY:-1000}"
DTYPE="${DTYPE:-bfloat16}"

mkdir -p "$RUN_ROOT"

run_variant() {
  local gpu="$1"
  local label="$2"
  local lr="$3"
  local loss_decay="$4"
  local topk_weight="$5"
  local topk_k="$6"
  local topk_margin="$7"
  local out="$RUN_ROOT/$label"
  mkdir -p "$out"
  (
    set -euo pipefail
    cd "$repo_dir"
    unset ONEAPI_DEVICE_SELECTOR
    export ZE_AFFINITY_MASK="$gpu"
    "$PY" scripts/train-qwen27-ex0bit-eagle3-adapter.py \
      --dataset-dir "$CORPUS/shard-0/dataset" \
      --dataset-dir "$CORPUS/shard-1/dataset" \
      --dataset-dir "$CORPUS/shard-2/dataset" \
      --heldout-dir "$CORPUS/shard-3/dataset" \
      --draft-dir "$START_DRAFT" \
      --target-model "$TARGET_MODEL" \
      --out-dir "$out/checkpoint" \
      --train-scope fc-lm-head \
      --rollout-steps 5 \
      --rollout-loss-decay "$loss_decay" \
      --rollout-survival-mode hard \
      --rollout-dead-loss-floor 0.05 \
      --rollout-rank-loss-weight 0.1 \
      --rollout-rank-margin 0.0 \
      --rollout-topk-rank-loss-weight "$topk_weight" \
      --rollout-topk-rank-k "$topk_k" \
      --rollout-topk-rank-margin "$topk_margin" \
      --epochs "$EPOCHS" \
      --batch-size "$BATCH_SIZE" \
      --lr "$lr" \
      --max-train-rows "$MAX_TRAIN_ROWS" \
      --max-heldout-rows "$MAX_HELDOUT_ROWS" \
      --eval-every "$EVAL_EVERY" \
      --dtype "$DTYPE" \
      --device xpu:0 \
      > "$out/train-stdout.log" 2>&1

    "$PY" scripts/evaluate-qwen27-ex0bit-eagle3-offline.py \
      --dataset-dir "$CORPUS/shard-3/dataset" \
      --draft-dir "$out/checkpoint" \
      --target-model "$TARGET_MODEL" \
      --max-steps 5 \
      --max-starts 0 \
      --topk 5 \
      --dtype "$DTYPE" \
      --device xpu:0 \
      --print-every 4096 \
      --out "$out/heldout-rollout-all-summary.json" \
      > "$out/heldout-rollout-all-stdout.log" 2>&1
  )
}

variants=(
  "0|rankpush-k64-w0p25-m0-lr1e-5-d0p25|1e-5|0.25|0.25|64|0.0"
  "1|rankpush-k64-w0p5-m0-lr5e-6-d0p25|5e-6|0.25|0.5|64|0.0"
  "2|rankpush-k128-w0p5-m0-lr5e-6-d0p25|5e-6|0.25|0.5|128|0.0"
  "3|rankpush-k64-w1-m0p1-lr3e-6-d0p5|3e-6|0.5|1.0|64|0.1"
)

pids=()
for item in "${variants[@]}"; do
  IFS='|' read -r gpu label lr loss_decay topk_weight topk_k topk_margin <<< "$item"
  echo "launch label=$label gpu=$gpu lr=$lr decay=$loss_decay topk_weight=$topk_weight topk_k=$topk_k margin=$topk_margin start=$START_DRAFT"
  run_variant "$gpu" "$label" "$lr" "$loss_decay" "$topk_weight" "$topk_k" "$topk_margin" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

exit "$rc"
