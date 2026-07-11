#!/usr/bin/env bash
set -euo pipefail

# Train four MTP3-specific FC candidates on the disjoint v6 chat corpus, then
# evaluate each candidate on the fixed-suite target continuations.  The latter
# is an acceptance diagnostic only; it is never a throughput record.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
TRAIN_DATA_ROOT="${TRAIN_DATA_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z}"
FIXED_SUITE_DATASET="${FIXED_SUITE_DATASET:-/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/fullcontext-fixed-suite-20260711T071359Z/corpus/shard-3/dataset}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-position-fc/mtp3-4gpu-$STAMP}"
TRAIN_STARTS="${TRAIN_STARTS:-16384}"
HELDOUT_STARTS="${HELDOUT_STARTS:-8192}"
HELDOUT_SAMPLES="${HELDOUT_SAMPLES:-288}"
BATCH_SIZE="${BATCH_SIZE:-4}"

labels=(lr1e5 lr2e5 lr3e5 lr5e5)
lrs=(1e-5 2e-5 3e-5 5e-5)
dataset_args=()
for shard in 0 1 2 3; do
  dataset_args+=(--dataset-dir "$TRAIN_DATA_ROOT/shard-$shard/dataset")
done

mkdir -p "$OUT_ROOT"
pids=()
for gpu in 0 1 2 3; do
  label="${labels[$gpu]}"
  out="$OUT_ROOT/$label"
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
      --max-steps 3
      --heldout-samples "$HELDOUT_SAMPLES"
      --train-starts "$TRAIN_STARTS"
      --heldout-starts "$HELDOUT_STARTS"
      --batch-size "$BATCH_SIZE"
      --epochs 1
      --lr "${lrs[$gpu]}"
      --scope position-fc
      --loss-mode all-steps
      --draft-lm-head int4-dequant
      --draft-lm-head-group-size 128
      --draft-lm-head-scale-dtype bf16
      --seed 27
      --print-every 100
    )
    printf '%q ' "${args[@]}" > "$out/train-command.txt"
    printf '\n' >> "$out/train-command.txt"
    "${args[@]}" > "$out/train.log" 2>&1

    eval_args=(
      "$PYTHON" "$ROOT/scripts/evaluate-qwen27-intrinsic-mtp-offline.py"
      --model-dir "$MODEL_DIR"
      --model-extra-path "$out/model_extra_tensors.safetensors"
      --dataset-dir "$FIXED_SUITE_DATASET"
      --max-steps 3
      --max-starts 8192
      --draft-lm-head int4-dequant
      --draft-lm-head-group-size 128
      --draft-lm-head-scale-dtype bf16
      --out "$out/fixed-suite-mtp3-eval.json"
      --print-every 100
    )
    printf '%q ' "${eval_args[@]}" > "$out/eval-command.txt"
    printf '\n' >> "$out/eval-command.txt"
    "${eval_args[@]}" > "$out/eval.log" 2>&1
  ) &
  pids+=("$!")
done

rc=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "${labels[$i]} failed; inspect $OUT_ROOT/${labels[$i]}" >&2
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
    path = root / label / "fixed-suite-mtp3-eval.json"
    if not path.exists():
        rows.append({"label": label, "status": "missing", "path": str(path)})
        continue
    data = json.loads(path.read_text())
    rows.append({
        "label": label,
        "status": "complete",
        "starts": data.get("starts"),
        "accepted_drafts_per_start": data.get("mean_accepted_draft_tokens"),
        "visible_tokens_per_step": data.get("mean_visible_tokens_if_k_step_spec"),
        "conditional_exact": data.get("conditional_exact"),
        "families": data.get("families"),
        "artifact": str(path),
    })
summary = {
    "classification": "diagnostic_mtp3_position_fc_fixed_suite_acceptance",
    "valid_headline_throughput": False,
    "training_data": "disjoint v6 chat target trajectories",
    "evaluation_data": "fixed realistic suite target continuations",
    "endpoint_trial_gate": {
        "minimum_delta_accepted_drafts_per_start": 0.205609,
        "reference_shared_accepted_drafts_per_start": 1.0128314798973481,
    },
    "rows": rows,
}
(root / "fixed-suite-summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT"
exit "$rc"
