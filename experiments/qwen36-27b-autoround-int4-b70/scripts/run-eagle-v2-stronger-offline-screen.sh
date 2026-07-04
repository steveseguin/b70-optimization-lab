#!/usr/bin/env bash
set -euo pipefail

# Diagnostic-only EAGLE v2 stronger-draft screen for Qwen3.6 27B AutoRound.
#
# This does not start an endpoint, does not touch LocalMaxxing, and must not be
# used as a throughput claim. It tests whether a materially stronger local EAGLE
# draft can improve held-out offline acceptance enough to justify a later,
# separate strict endpoint validation plan.

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
V2_ROOT="${V2_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260704T102338Z}"
CALIB_DATASET="${CALIB_DATASET:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-calib-20260704T101119Z/dataset}"
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle-v2-stronger-offline-${STAMP}}"
SUMMARY_OUT="${SUMMARY_OUT:-data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-v2-stronger-offline-${STAMP}-summary.json}"
MAX_STARTS="${MAX_STARTS:-2048}"
EVAL_DTYPE="${EVAL_DTYPE:-bfloat16}"

mkdir -p "$RUN_ROOT/logs" "$(dirname "$SUMMARY_OUT")"

train_shard_0="$V2_ROOT/shard-0/dataset"
train_shard_1="$V2_ROOT/shard-1/dataset"
train_shard_2="$V2_ROOT/shard-2/dataset"
heldout_shard_3="$V2_ROOT/shard-3/dataset"

for path in "$MODEL_DIR" "$train_shard_0" "$train_shard_1" "$train_shard_2" "$heldout_shard_3" "$CALIB_DATASET"; do
  if [[ ! -e "$path" ]]; then
    echo "missing required path: $path" >&2
    exit 1
  fi
done

run_variant() {
  local label="$1"
  local gpu="$2"
  local eval_kind="$3"
  shift 3

  local out_dir="$RUN_ROOT/$label"
  local train_log="$RUN_ROOT/logs/train-${label}.stdout.log"
  local eval_log="$RUN_ROOT/logs/eval-${label}.stdout.log"
  local eval_json="$RUN_ROOT/eval-${label}.json"
  mkdir -p "$out_dir"

  local eval_args=()
  if [[ "$eval_kind" == "heldout-shard3" ]]; then
    eval_args+=(--dataset-dir "$heldout_shard_3")
  elif [[ "$eval_kind" == "calib-v2" ]]; then
    eval_args+=(--dataset-dir "$CALIB_DATASET")
  else
    echo "unknown eval kind: $eval_kind" >&2
    return 2
  fi

  (
    set -euo pipefail
    # On this host, ZE_AFFINITY_MASK=N remaps physical B70 N to xpu:0 for the
    # process. Combining it with ONEAPI_DEVICE_SELECTOR=level_zero:N makes
    # torch.xpu report zero devices for N>0, so intentionally leave the latter
    # unset for per-GPU training/eval isolation.
    unset ONEAPI_DEVICE_SELECTOR
    export ZE_AFFINITY_MASK="${gpu}"
    export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export PYTHONPATH="/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels${PYTHONPATH:+:$PYTHONPATH}"

    "$PYTHON" scripts/train-qwen36-eagle1-draft.py \
      --target-model "$MODEL_DIR" \
      --out-dir "$out_dir" \
      "$@" \
      > "$train_log" 2>&1

    "$PYTHON" scripts/evaluate-qwen36-eagle-draft-offline.py \
      "${eval_args[@]}" \
      --draft-dir "$out_dir" \
      --target-model "$MODEL_DIR" \
      --max-steps 3 \
      --max-starts "$MAX_STARTS" \
      --start-stride 1 \
      --dtype "$EVAL_DTYPE" \
      --topk 3 \
      --out "$eval_json" \
      > "$eval_log" 2>&1
  )
}

pids=()

run_variant \
  v2-shards012-r3-e8-lr2e5-i8192-max160-tok01 \
  0 heldout-shard3 \
  --dataset-dir "$train_shard_0" \
  --dataset-dir "$train_shard_1" \
  --dataset-dir "$train_shard_2" \
  --num-layers 1 \
  --intermediate-size 8192 \
  --epochs 8 \
  --rollout-steps 3 \
  --lr 2e-5 \
  --max-len 160 \
  --token-loss-weight 0.1 \
  --train-dtype float32 \
  --export-dtype bfloat16 \
  --log-every 24 &
pids+=("$!")

run_variant \
  v2-shards012-r3-e8-lr1e5-i12288-max160-tok02 \
  1 heldout-shard3 \
  --dataset-dir "$train_shard_0" \
  --dataset-dir "$train_shard_1" \
  --dataset-dir "$train_shard_2" \
  --num-layers 1 \
  --intermediate-size 12288 \
  --epochs 8 \
  --rollout-steps 3 \
  --lr 1e-5 \
  --max-len 160 \
  --token-loss-weight 0.2 \
  --train-dtype float32 \
  --export-dtype bfloat16 \
  --log-every 24 &
pids+=("$!")

run_variant \
  v2-shards012-r3-layer2-residual-e6-lr2e5-max160 \
  2 heldout-shard3 \
  --dataset-dir "$train_shard_0" \
  --dataset-dir "$train_shard_1" \
  --dataset-dir "$train_shard_2" \
  --init-checkpoint "$V2_ROOT/draft-v2-staged-r3-e2-lr3e5-max128" \
  --residual-extra-init-layer \
  --num-layers 2 \
  --intermediate-size 4096 \
  --epochs 6 \
  --rollout-steps 3 \
  --lr 2e-5 \
  --max-len 160 \
  --token-loss-weight 0.1 \
  --train-dtype float32 \
  --export-dtype bfloat16 \
  --log-every 24 &
pids+=("$!")

run_variant \
  v2-all96-r3-e8-lr2e5-i8192-max160-calib \
  3 calib-v2 \
  --dataset-dir "$train_shard_0" \
  --dataset-dir "$train_shard_1" \
  --dataset-dir "$train_shard_2" \
  --dataset-dir "$heldout_shard_3" \
  --num-layers 1 \
  --intermediate-size 8192 \
  --epochs 8 \
  --rollout-steps 3 \
  --lr 2e-5 \
  --max-len 160 \
  --token-loss-weight 0.1 \
  --train-dtype float32 \
  --export-dtype bfloat16 \
  --log-every 24 &
pids+=("$!")

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

"$PYTHON" - "$RUN_ROOT" "$SUMMARY_OUT" "$MODEL_DIR" "$V2_ROOT" "$CALIB_DATASET" "$MAX_STARTS" <<'PY'
import json
import sys
from pathlib import Path

run_root = Path(sys.argv[1])
summary_out = Path(sys.argv[2])
model_dir = sys.argv[3]
v2_root = sys.argv[4]
calib_dataset = sys.argv[5]
max_starts = int(sys.argv[6])

rows = []
for eval_path in sorted(run_root.glob("eval-*.json")):
    data = json.loads(eval_path.read_text())
    label = eval_path.stem.removeprefix("eval-")
    hist = data.get("acceptance_histogram") or {}
    per_step = data.get("per_step") or []
    rows.append({
        "label": label,
        "eval_path": str(eval_path),
        "draft_dir": data.get("draft_dir"),
        "dataset_dir": data.get("dataset_dir"),
        "starts": data.get("starts"),
        "mean_accepted": data.get("mean_accepted"),
        "histogram": hist,
        "step1_exact": (per_step[0].get("exact_rate") if len(per_step) > 0 else None),
        "step2_conditional": (per_step[1].get("exact_rate") if len(per_step) > 1 else None),
        "step3_conditional": (per_step[2].get("exact_rate") if len(per_step) > 2 else None),
        "family_rows": data.get("family_rows", []),
    })

rows.sort(key=lambda x: (x.get("mean_accepted") or -1), reverse=True)
best = rows[0] if rows else None
summary = {
    "classification": "diagnostic_only_eagle_v2_stronger_offline_screen",
    "date": "2026-07-04",
    "run_root": str(run_root),
    "model_dir": model_dir,
    "v2_root": v2_root,
    "calib_dataset": calib_dataset,
    "max_starts": max_starts,
    "promotion_policy": (
        "Offline acceptance is not a speed result. Do not endpoint-test unless "
        "held-out acceptance moves materially near the old >2.0 mean-accepted "
        "bar and anti-repetition/quality risks are separately addressed."
    ),
    "endpoint_candidate_threshold": {
        "mean_accepted_min": 2.0,
        "step3_conditional_min": 0.65,
    },
    "rows": rows,
    "best": best,
    "decision": (
        "endpoint_candidate"
        if best
        and (best.get("mean_accepted") or 0) >= 2.0
        and (best.get("step3_conditional") or 0) >= 0.65
        else "no_endpoint_candidate"
    ),
}
summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
(run_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

exit "$rc"
