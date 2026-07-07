#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-fullvocab-5aux-rankpush-${STAMP}}"
CORPUS="${CORPUS:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v7-5aux-v6b-4gpu-20260707T095940Z}"
TARGET_MODEL="${TARGET_MODEL:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
DRAFT="${DRAFT:-/mnt/fast-ai/llm-cache/hf/manual/Ex0bit--Qwen3.6-27B-PRISM-EAGLE3/full}"
PY="${PY:-/home/steve/.venvs/vllm-xpu/bin/python}"
DTYPE="${DTYPE:-bfloat16}"

mkdir -p "$RUN_ROOT"

run_variant() {
  local gpu="$1"
  local label="$2"
  local lr="$3"
  local decay="$4"
  local rank_weight="$5"
  local topk_rank_weight="$6"
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
      --draft-dir "$DRAFT" \
      --target-model "$TARGET_MODEL" \
      --out-dir "$out/checkpoint" \
      --aux-count 5 \
      --aux-source-target-slots 0,2,4 \
      --train-scope fc-lm-head \
      --rollout-steps 5 \
      --rollout-loss-decay "$decay" \
      --rollout-survival-mode hard \
      --rollout-dead-loss-floor 0.05 \
      --rollout-rank-loss-weight "$rank_weight" \
      --rollout-topk-rank-loss-weight "$topk_rank_weight" \
      --rollout-topk-rank-k 128 \
      --epochs "${EPOCHS:-2}" \
      --batch-size "${BATCH_SIZE:-2}" \
      --lr "$lr" \
      --max-train-rows "${MAX_TRAIN_ROWS:-32768}" \
      --max-heldout-rows "${MAX_HELDOUT_ROWS:-8192}" \
      --eval-every "${EVAL_EVERY:-500}" \
      --dtype "$DTYPE" \
      --device xpu:0 \
      > "$out/train.log" 2>&1

    "$PY" scripts/evaluate-qwen27-ex0bit-eagle3-offline.py \
      --dataset-dir "$CORPUS/shard-3/dataset" \
      --draft-dir "$out/checkpoint" \
      --target-model "$TARGET_MODEL" \
      --aux-count 5 \
      --aux-source-target-slots 0,2,4 \
      --max-steps 5 \
      --max-starts 0 \
      --topk 128 \
      --dtype "$DTYPE" \
      --device xpu:0 \
      --out "$out/heldout-top1-summary.json" \
      > "$out/eval-top1.log" 2>&1

    "$PY" scripts/evaluate-qwen27-ex0bit-eagle3-offline.py \
      --dataset-dir "$CORPUS/shard-3/dataset" \
      --draft-dir "$out/checkpoint" \
      --target-model "$TARGET_MODEL" \
      --aux-count 5 \
      --aux-source-target-slots 0,2,4 \
      --accept-mode topk-oracle \
      --max-steps 5 \
      --max-starts 0 \
      --topk 128 \
      --dtype "$DTYPE" \
      --device xpu:0 \
      --out "$out/heldout-top128-oracle-summary.json" \
      > "$out/eval-top128-oracle.log" 2>&1
  )
}

variants=(
  "0|fullvocab-5aux-lr3e-6-decay0p5-rank0p1-topk0p25|3e-6|0.5|0.1|0.25"
  "1|fullvocab-5aux-lr1e-6-decay0p5-rank0p1-topk0p25|1e-6|0.5|0.1|0.25"
  "2|fullvocab-5aux-lr3e-6-decay0p25-rank0p2-topk0p5|3e-6|0.25|0.2|0.5"
  "3|fullvocab-5aux-lr1e-6-decay0p25-rank0p2-topk0p5|1e-6|0.25|0.2|0.5"
)

pids=()
for item in "${variants[@]}"; do
  IFS='|' read -r gpu label lr decay rank_weight topk_rank_weight <<< "$item"
  echo "launch label=$label gpu=$gpu lr=$lr decay=$decay rank=$rank_weight topk_rank=$topk_rank_weight"
  run_variant "$gpu" "$label" "$lr" "$decay" "$rank_weight" "$topk_rank_weight" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

cat > "$RUN_ROOT/README.md" <<EOF
# Qwen27 full-vocab five-aux EAGLE3 rank-push screen

Diagnostic-only stronger-drafter acceptance screen. This is not endpoint
throughput, not a quality result, and not LocalMaxxing-submittable.

- target: $TARGET_MODEL
- draft source: $DRAFT
- corpus: $CORPUS
- run root: $RUN_ROOT

Promote nothing unless a later strict fresh endpoint run passes cached-zero,
quality, and variance gates.
EOF

exit "$rc"
