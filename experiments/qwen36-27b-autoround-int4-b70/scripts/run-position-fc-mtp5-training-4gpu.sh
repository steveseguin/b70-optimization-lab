#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
DATA_ROOT="${DATA_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-position-fc/mtp5-4gpu-$STAMP}"
TRAIN_STARTS="${TRAIN_STARTS:-16384}"
HELDOUT_STARTS="${HELDOUT_STARTS:-8192}"
HELDOUT_SAMPLES="${HELDOUT_SAMPLES:-288}"
BATCH_SIZE="${BATCH_SIZE:-4}"
EPOCHS="${EPOCHS:-1}"

mkdir -p "$OUT_ROOT"

dataset_args=()
for shard in 0 1 2 3; do
  dataset_args+=(--dataset-dir "$DATA_ROOT/shard-$shard/dataset")
done

run_one() {
  local gpu="$1"
  local label="$2"
  local lr="$3"
  local freeze="$4"
  local loss_mode="$5"
  local out="$OUT_ROOT/$label"
  mkdir -p "$out"
  (
    export ZE_AFFINITY_MASK="$gpu"
    export PYTHONPATH="/home/steve/src/vllm${PYTHONPATH:+:$PYTHONPATH}"
    export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    args=(
      "$PYTHON" "$ROOT/scripts/train-qwen27-intrinsic-mtp-adapter.py"
      --model-dir "$MODEL_DIR"
      "${dataset_args[@]}"
      --out-dir "$out"
      --max-steps 5
      --heldout-samples "$HELDOUT_SAMPLES"
      --train-starts "$TRAIN_STARTS"
      --heldout-starts "$HELDOUT_STARTS"
      --batch-size "$BATCH_SIZE"
      --epochs "$EPOCHS"
      --lr "$lr"
      --scope position-fc
      --loss-mode "$loss_mode"
      --draft-lm-head int4-dequant
      --draft-lm-head-group-size 128
      --draft-lm-head-scale-dtype bf16
      --seed 27
      --print-every 100
    )
    if [[ -n "$freeze" ]]; then
      args+=(--freeze-position-fcs "$freeze")
    fi
    printf '%q ' "${args[@]}" > "$out/command.txt"
    printf '\n' >> "$out/command.txt"
    "${args[@]}" > "$out/train.log" 2>&1
  ) &
  pids+=("$!")
}

pids=()
labels=(
  allfc-allsteps-lr2e5
  freeze0-cond-lr2e5
  freeze01-cond-lr2e5
  freeze0-cond-lr1e5
)
run_one 0 "${labels[0]}" 2e-5 "" all-steps
run_one 1 "${labels[1]}" 2e-5 0 conditional-prefix
run_one 2 "${labels[2]}" 2e-5 0,1 conditional-prefix
run_one 3 "${labels[3]}" 1e-5 0 conditional-prefix

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
        "loss_mode": data.get("loss_mode"),
        "lr": data.get("lr"),
        "frozen": data.get("position_fc_frozen_indices"),
        "trainable": data.get("position_fc_trainable_indices"),
        "before": data.get("before"),
        "after": data.get("after"),
        "elapsed_s": data.get("elapsed_s"),
        "skipped_no_trainable_prefix_batches": data.get(
            "skipped_no_trainable_prefix_batches"
        ),
        "model_extra": str(root / label / "model_extra_tensors.safetensors"),
    })
summary = {
    "classification": "diagnostic_position_specific_mtp5_training_matrix",
    "valid_headline_throughput": False,
    "headline_warning": "Offline acceptance only; not LocalMaxxing eligible.",
    "rows": rows,
}
(root / "matrix-summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT"
exit "$rc"
