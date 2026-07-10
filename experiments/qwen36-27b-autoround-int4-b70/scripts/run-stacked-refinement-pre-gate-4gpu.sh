#!/usr/bin/env bash
set -euo pipefail

# Four-GPU offline acceptance pre-gate for one additional full MTP refinement
# layer. These are diagnostic training rows, not endpoint throughput results.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
DATA_ROOT="${DATA_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-stacked-refinement/mtp5-pre-gate-4gpu-$STAMP}"
TRAIN_STARTS="${TRAIN_STARTS:-8192}"
HELDOUT_STARTS="${HELDOUT_STARTS:-4096}"
HELDOUT_SAMPLES="${HELDOUT_SAMPLES:-16}"
BATCH_SIZE="${BATCH_SIZE:-4}"
MAX_TRAIN_STEPS="${MAX_TRAIN_STEPS:-1024}"

mkdir -p "$OUT_ROOT"
dataset_args=()
for shard in 0 1 2 3; do
  dataset_args+=(--dataset-dir "$DATA_ROOT/shard-$shard/dataset")
done

run_one() {
  local gpu="$1"
  local label="$2"
  local scope="$3"
  local loss_mode="$4"
  local lr="$5"
  local out="$OUT_ROOT/$label"
  mkdir -p "$out"
  (
    export ZE_AFFINITY_MASK="$gpu"
    export ONEAPI_DEVICE_SELECTOR=level_zero:0
    export PYTHONPATH="/home/steve/src/vllm${PYTHONPATH:+:$PYTHONPATH}"
    export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    args=(
      "$PYTHON" "$ROOT/scripts/train-qwen27-stacked-mtp-refinement.py"
      --model-dir "$MODEL_DIR"
      "${dataset_args[@]}"
      --out-dir "$out"
      --max-steps 5
      --heldout-samples "$HELDOUT_SAMPLES"
      --train-starts "$TRAIN_STARTS"
      --heldout-starts "$HELDOUT_STARTS"
      --batch-size "$BATCH_SIZE"
      --epochs 1
      --max-train-steps "$MAX_TRAIN_STEPS"
      --lr "$lr"
      --weight-decay 0
      --scope "$scope"
      --loss-mode "$loss_mode"
      --draft-lm-head int4-dequant
      --draft-lm-head-group-size 128
      --draft-lm-head-scale-dtype bf16
      --skip-official-rope
      --seed 27
      --print-every 100
    )
    printf '%q ' "${args[@]}" > "$out/command.txt"
    printf '\n' >> "$out/command.txt"
    "${args[@]}" > "$out/train.log" 2>&1
  ) &
  pids+=("$!")
  labels+=("$label")
}

pids=()
labels=()
run_one 0 full-all-lr2e-6 full all-steps 2e-6
run_one 1 full-conditional-lr2e-6 full conditional-prefix 2e-6
run_one 2 attn-all-lr5e-6 attn all-steps 5e-6
run_one 3 mlp-all-lr5e-6 mlp all-steps 5e-6

rc=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "${labels[$i]} failed; see $OUT_ROOT/${labels[$i]}/train.log" >&2
    rc=1
  fi
done

"$PYTHON" - "$OUT_ROOT" "${labels[@]}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for label in sys.argv[2:]:
    path = root / label / "training_summary.json"
    if not path.exists():
        rows.append({"label": label, "status": "missing", "path": str(path)})
        continue
    data = json.loads(path.read_text())
    rows.append({
        "label": label,
        "status": "complete",
        "scope": data.get("scope"),
        "loss_mode": data.get("loss_mode"),
        "lr": data.get("lr"),
        "base_only": data.get("base_only"),
        "before": data.get("before"),
        "after": data.get("after"),
        "training": data.get("training"),
        "trainable_param_count": data.get("trainable_param_count"),
        "artifact": data.get("artifact"),
    })
summary = {
    "classification": "diagnostic_stacked_mtp_refinement_pre_gate",
    "valid_headline_throughput": False,
    "localmaxxing_eligible": False,
    "endpoint_trial_visible_tokens_gate": 3.3,
    "headline_warning": (
        "Offline acceptance only; endpoint runtime integration and strict fresh "
        "validation are required before any throughput claim."
    ),
    "rows": rows,
}
(root / "matrix-summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT"
exit "$rc"
