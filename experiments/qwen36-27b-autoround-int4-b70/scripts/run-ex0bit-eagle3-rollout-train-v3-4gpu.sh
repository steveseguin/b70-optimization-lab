#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-rollouttrain-v3-4gpu-${STAMP}}"
CORPUS="${CORPUS:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v2-chat-4gpu-20260706T195742Z}"
TARGET_MODEL="${TARGET_MODEL:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
ORIGINAL_DRAFT="${ORIGINAL_DRAFT:-/mnt/fast-ai/llm-cache/hf/manual/Ex0bit--Qwen3.6-27B-PRISM-EAGLE3/compressed}"
ADAPTED_DRAFT="${ADAPTED_DRAFT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-fcheadadapt-v3full-20260706T200821Z/checkpoint}"
PY="${PY:-/home/steve/.venvs/vllm-xpu/bin/python}"
BATCH_SIZE="${BATCH_SIZE:-64}"
EPOCHS="${EPOCHS:-6}"
MAX_TRAIN_ROWS="${MAX_TRAIN_ROWS:-0}"
MAX_HELDOUT_ROWS="${MAX_HELDOUT_ROWS:-0}"
EVAL_EVERY="${EVAL_EVERY:-1000}"
DTYPE="${DTYPE:-bfloat16}"
SWEEP="${SWEEP:-mixed}"

mkdir -p "$RUN_ROOT"

run_variant() {
  local gpu="$1"
  local label="$2"
  local draft="$3"
  local steps="$4"
  local decay="$5"
  local lr="$6"
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
      --draft-dir "$draft" \
      --target-model "$TARGET_MODEL" \
      --out-dir "$out/checkpoint" \
      --train-scope fc-lm-head \
      --rollout-steps "$steps" \
      --rollout-loss-decay "$decay" \
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

case "$SWEEP" in
  mixed)
    variants=(
      "0|v3full-r3-lr3e-6-decay1|$ADAPTED_DRAFT|3|1.0|3e-6"
      "1|v3full-r3-lr3e-6-decay1p5|$ADAPTED_DRAFT|3|1.5|3e-6"
      "2|v3full-r5-lr2e-6-decay1|$ADAPTED_DRAFT|5|1.0|2e-6"
      "3|original-r3-lr1e-5-decay1|$ORIGINAL_DRAFT|3|1.0|1e-5"
    )
    ;;
  original-rollout)
    variants=(
      "0|original-r3-lr5e-6-decay1|$ORIGINAL_DRAFT|3|1.0|5e-6"
      "1|original-r3-lr1e-5-decay1p5|$ORIGINAL_DRAFT|3|1.5|1e-5"
      "2|original-r3-lr2e-5-decay1|$ORIGINAL_DRAFT|3|1.0|2e-5"
      "3|original-r5-lr1e-5-decay1|$ORIGINAL_DRAFT|5|1.0|1e-5"
    )
    ;;
  *)
    echo "Unknown SWEEP=$SWEEP (expected mixed or original-rollout)" >&2
    exit 2
    ;;
esac

pids=()
for item in "${variants[@]}"; do
  IFS='|' read -r gpu label draft steps decay lr <<< "$item"
  echo "launch label=$label gpu=$gpu steps=$steps decay=$decay lr=$lr draft=$draft"
  run_variant "$gpu" "$label" "$draft" "$steps" "$decay" "$lr" &
  pids+=("$!")
done

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

python3 - "$RUN_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for variant in sorted(p for p in root.iterdir() if p.is_dir()):
    train_meta_path = variant / "checkpoint" / "training_meta.json"
    rollout_path = variant / "heldout-rollout-all-summary.json"
    row = {
        "label": variant.name,
        "path": str(variant),
        "train_meta_exists": train_meta_path.exists(),
        "rollout_summary_exists": rollout_path.exists(),
    }
    if train_meta_path.exists():
        train = json.loads(train_meta_path.read_text())
        row.update({
            "train_objective": train.get("train_objective"),
            "rollout_steps": train.get("rollout_steps"),
            "rollout_loss_decay": train.get("rollout_loss_decay"),
            "lr": train.get("lr"),
            "final_train_exact": (train.get("final_train") or {}).get("exact_rate"),
            "final_heldout_exact": (train.get("final_heldout") or {}).get("exact_rate"),
            "elapsed_s": train.get("elapsed_s"),
        })
    if rollout_path.exists():
        rollout = json.loads(rollout_path.read_text())
        per_step = rollout.get("per_step") or []
        row.update({
            "starts": rollout.get("starts"),
            "mean_accepted": rollout.get("mean_accepted"),
            "histogram": rollout.get("acceptance_histogram"),
            "step1_exact": (per_step[0] or {}).get("exact_rate") if len(per_step) > 0 else None,
            "step2_conditional_exact": (per_step[1] or {}).get("exact_rate") if len(per_step) > 1 else None,
            "step3_conditional_exact": (per_step[2] or {}).get("exact_rate") if len(per_step) > 2 else None,
        })
    rows.append(row)
summary = {
    "classification": "diagnostic_only_qwen27_ex0bit_eagle3_rollout_training_screen",
    "valid_headline_throughput": False,
    "run_root": str(root),
    "rows": rows,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "$RUN_ROOT"
exit "$rc"
