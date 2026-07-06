#!/usr/bin/env bash
set -euo pipefail

# Diagnostic-only Qwen27 EAGLE large-corpus offline screen.
#
# This trains candidate EAGLE drafts on a non-final hidden-state corpus and
# evaluates every candidate on both a held-out shard and the separate small
# calibration set. It does not start a serving endpoint, does not claim
# throughput, and must not be submitted to LocalMaxxing.

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_dir"

PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
CALIB_DATASET="${CALIB_DATASET:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-calib-20260704T101119Z/dataset}"
V3_ROOT="${V3_ROOT:-}"
if [[ -z "$V3_ROOT" ]]; then
  V3_ROOT="$(find /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data \
    -maxdepth 1 -type d -name 'qwen27-eagledata-v2-chat-4gpu-20260706T*' \
    | sort | tail -1)"
fi
if [[ -z "$V3_ROOT" ]]; then
  echo "V3_ROOT is required or no 20260706 4-GPU corpus root was found" >&2
  exit 1
fi
RUN_ROOT="${RUN_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle-v4-large-offline-${STAMP}}"
SUMMARY_OUT="${SUMMARY_OUT:-data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-v4-large-offline-${STAMP}-summary.json}"
MAX_STARTS="${MAX_STARTS:-4096}"
EVAL_DTYPE="${EVAL_DTYPE:-bfloat16}"
STAGED_INIT="${STAGED_INIT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260704T102338Z/draft-v2-staged-r3-e2-lr3e5-max128}"

mkdir -p "$RUN_ROOT/logs" "$(dirname "$SUMMARY_OUT")"

train_shard_0="$V3_ROOT/shard-0/dataset"
train_shard_1="$V3_ROOT/shard-1/dataset"
train_shard_2="$V3_ROOT/shard-2/dataset"
heldout_shard_3="$V3_ROOT/shard-3/dataset"

required_paths=(
  "$MODEL_DIR"
  "$train_shard_0"
  "$train_shard_1"
  "$train_shard_2"
  "$heldout_shard_3"
  "$CALIB_DATASET"
)
for path in "${required_paths[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "missing required path: $path" >&2
    exit 1
  fi
done

run_variant() {
  local label="$1"
  local gpu="$2"
  shift 2

  local out_dir="$RUN_ROOT/$label"
  local train_log="$RUN_ROOT/logs/train-${label}.stdout.log"
  local heldout_log="$RUN_ROOT/logs/eval-heldout-${label}.stdout.log"
  local calib_log="$RUN_ROOT/logs/eval-calib-${label}.stdout.log"
  local heldout_json="$RUN_ROOT/eval-heldout-${label}.json"
  local calib_json="$RUN_ROOT/eval-calib-${label}.json"
  mkdir -p "$out_dir"

  (
    set -euo pipefail
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
      --dataset-dir "$heldout_shard_3" \
      --draft-dir "$out_dir" \
      --target-model "$MODEL_DIR" \
      --max-steps 3 \
      --max-starts "$MAX_STARTS" \
      --start-stride 1 \
      --dtype "$EVAL_DTYPE" \
      --topk 3 \
      --out "$heldout_json" \
      > "$heldout_log" 2>&1

    "$PYTHON" scripts/evaluate-qwen36-eagle-draft-offline.py \
      --dataset-dir "$CALIB_DATASET" \
      --draft-dir "$out_dir" \
      --target-model "$MODEL_DIR" \
      --max-steps 3 \
      --max-starts "$MAX_STARTS" \
      --start-stride 1 \
      --dtype "$EVAL_DTYPE" \
      --topk 3 \
      --out "$calib_json" \
      > "$calib_log" 2>&1
  )
}

pids=()

run_variant \
  v4-large-r3-e4-lr2e5-i8192-max160-tok01 \
  0 \
  --dataset-dir "$train_shard_0" \
  --dataset-dir "$train_shard_1" \
  --dataset-dir "$train_shard_2" \
  --num-layers 1 \
  --intermediate-size 8192 \
  --epochs 4 \
  --rollout-steps 3 \
  --lr 2e-5 \
  --max-len 160 \
  --token-loss-weight 0.1 \
  --train-dtype float32 \
  --export-dtype bfloat16 \
  --log-every 96 &
pids+=("$!")

run_variant \
  v4-large-r3-e4-lr1e5-i12288-max160-tok02 \
  1 \
  --dataset-dir "$train_shard_0" \
  --dataset-dir "$train_shard_1" \
  --dataset-dir "$train_shard_2" \
  --num-layers 1 \
  --intermediate-size 12288 \
  --epochs 4 \
  --rollout-steps 3 \
  --lr 1e-5 \
  --max-len 160 \
  --token-loss-weight 0.2 \
  --train-dtype float32 \
  --export-dtype bfloat16 \
  --log-every 96 &
pids+=("$!")

if [[ -d "$STAGED_INIT" ]]; then
  run_variant \
    v4-large-residual2-initv2-r3-e5-lr2e5-max160 \
    2 \
    --dataset-dir "$train_shard_0" \
    --dataset-dir "$train_shard_1" \
    --dataset-dir "$train_shard_2" \
    --init-checkpoint "$STAGED_INIT" \
    --residual-extra-init-layer \
    --num-layers 2 \
    --intermediate-size 4096 \
    --epochs 5 \
    --rollout-steps 3 \
    --lr 2e-5 \
    --max-len 160 \
    --feature-loss-weight 0.2 \
    --token-loss-weight 0.5 \
    --train-dtype float32 \
    --export-dtype bfloat16 \
    --log-every 96 &
  pids+=("$!")
else
  echo "Skipping residual init variant; STAGED_INIT not found: $STAGED_INIT" >&2
fi

run_variant \
  v4-large-r3-e6-lr8e6-i8192-max160-token05 \
  3 \
  --dataset-dir "$train_shard_0" \
  --dataset-dir "$train_shard_1" \
  --dataset-dir "$train_shard_2" \
  --num-layers 1 \
  --intermediate-size 8192 \
  --epochs 6 \
  --rollout-steps 3 \
  --lr 8e-6 \
  --max-len 160 \
  --feature-loss-weight 0.5 \
  --token-loss-weight 0.5 \
  --train-dtype float32 \
  --export-dtype bfloat16 \
  --log-every 96 &
pids+=("$!")

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

"$PYTHON" - "$RUN_ROOT" "$SUMMARY_OUT" "$MODEL_DIR" "$V3_ROOT" "$CALIB_DATASET" "$MAX_STARTS" "$rc" <<'PY'
import json
import sys
from pathlib import Path

run_root = Path(sys.argv[1])
summary_out = Path(sys.argv[2])
model_dir = sys.argv[3]
v3_root = sys.argv[4]
calib_dataset = sys.argv[5]
max_starts = int(sys.argv[6])
variant_rc = int(sys.argv[7])


def load_eval(path: Path) -> dict:
    data = json.loads(path.read_text())
    per_step = data.get("per_step") or []
    return {
        "path": str(path),
        "starts": data.get("starts"),
        "mean_accepted": data.get("mean_accepted"),
        "histogram": data.get("acceptance_histogram") or {},
        "step1_exact": (per_step[0].get("exact_rate") if len(per_step) > 0 else None),
        "step2_conditional": (per_step[1].get("exact_rate") if len(per_step) > 1 else None),
        "step3_conditional": (per_step[2].get("exact_rate") if len(per_step) > 2 else None),
        "family_rows": data.get("family_rows", []),
    }


rows = []
for draft_dir in sorted(p for p in run_root.iterdir()
                        if p.is_dir() and p.name != "logs"):
    label = draft_dir.name
    train_summary_path = draft_dir / "summary.json"
    train_metrics_path = draft_dir / "training_metrics.json"
    heldout_path = run_root / f"eval-heldout-{label}.json"
    calib_path = run_root / f"eval-calib-{label}.json"
    row = {
        "label": label,
        "draft_dir": str(draft_dir),
        "train_summary": str(train_summary_path) if train_summary_path.exists() else None,
        "training_metrics": str(train_metrics_path) if train_metrics_path.exists() else None,
        "heldout": load_eval(heldout_path) if heldout_path.exists() else None,
        "calib": load_eval(calib_path) if calib_path.exists() else None,
    }
    heldout = row["heldout"] or {}
    calib = row["calib"] or {}
    row["endpoint_candidate"] = bool(
        (heldout.get("mean_accepted") or 0) >= 2.0
        and (heldout.get("step3_conditional") or 0) >= 0.65
        and (calib.get("mean_accepted") or 0) >= 1.5
    )
    rows.append(row)

rows.sort(
    key=lambda row: (
        (row.get("heldout") or {}).get("mean_accepted") or -1,
        (row.get("calib") or {}).get("mean_accepted") or -1,
    ),
    reverse=True,
)
best = rows[0] if rows else None
summary = {
    "classification": "diagnostic_only_eagle_v4_large_corpus_offline_screen",
    "date": "2026-07-06",
    "run_root": str(run_root),
    "model_dir": model_dir,
    "v3_root": v3_root,
    "calib_dataset": calib_dataset,
    "max_starts": max_starts,
    "variant_rc": variant_rc,
    "endpoint_policy": {
        "heldout_mean_accepted_min": 2.0,
        "heldout_step3_conditional_min": 0.65,
        "calib_mean_accepted_min": 1.5,
        "reason": (
            "Offline acceptance is not a speed claim. Endpoint validation is "
            "allowed only after a materially stronger draft clears held-out "
            "and separate-calibration acceptance gates."
        ),
    },
    "rows": rows,
    "best": best,
    "decision": (
        "endpoint_candidate"
        if any(row.get("endpoint_candidate") for row in rows)
        else "no_endpoint_candidate"
    ),
}
summary_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
(run_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

exit "$rc"
