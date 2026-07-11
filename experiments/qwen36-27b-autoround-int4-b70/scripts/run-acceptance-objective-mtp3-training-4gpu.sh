#!/usr/bin/env bash
set -euo pipefail

# Compare acceptance-aligned objectives for the graph-safe static position-FC
# MTP3 adapter. Training trajectories are disjoint from the fixed realistic
# continuation suite used only for the offline endpoint gate.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
TRAIN_DATA_ROOT="${TRAIN_DATA_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z}"
FIXED_SUITE_DATASET="${FIXED_SUITE_DATASET:-/mnt/usb-models/llm-optimization-artifacts/qwen27-dflash/fullcontext-fixed-suite-20260711T071359Z/corpus/shard-3/dataset}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-position-fc/acceptance-objective-mtp3-4gpu-$STAMP}"
TRAIN_STARTS="${TRAIN_STARTS:-16384}"
HELDOUT_STARTS="${HELDOUT_STARTS:-8192}"
HELDOUT_SAMPLES="${HELDOUT_SAMPLES:-288}"
BATCH_SIZE="${BATCH_SIZE:-4}"
LR="${LR:-2e-5}"
MATRIX="${MATRIX:-mixed}"

case "$MATRIX" in
  mixed)
    labels=(survival-w1 survival-w4 margin-w01 survival-w1-margin-w01)
    ;;
  margin)
    labels=(margin-w003 margin-w01 margin-w03 margin-w1)
    ;;
  conditional)
    labels=(conditional-lr1e5 conditional-lr2e5 conditional-margin-lr1e5 conditional-margin-lr2e5)
    ;;
  *)
    echo "unknown MATRIX=$MATRIX (expected mixed, margin, or conditional)" >&2
    exit 2
    ;;
esac
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
    objective_args=()
    candidate_lr="$LR"
    candidate_loss_mode=all-steps
    if [[ "$MATRIX" == "mixed" ]]; then
      case "$gpu" in
        0) objective_args+=(--expected-prefix-survival-weight 1.0) ;;
        1) objective_args+=(--expected-prefix-survival-weight 4.0) ;;
        2) objective_args+=(--target-top1-margin-weight 0.1 --target-top1-margin 1.0) ;;
        3) objective_args+=(--expected-prefix-survival-weight 1.0 --target-top1-margin-weight 0.1 --target-top1-margin 1.0) ;;
      esac
    elif [[ "$MATRIX" == "margin" ]]; then
      margin_weights=(0.03 0.1 0.3 1.0)
      objective_args+=(
        --target-top1-margin-weight "${margin_weights[$gpu]}"
        --target-top1-margin 1.0
      )
    else
      candidate_loss_mode=conditional-prefix
      case "$gpu" in
        0) candidate_lr=1e-5 ;;
        1) candidate_lr=2e-5 ;;
        2) candidate_lr=1e-5; objective_args+=(--target-top1-margin-weight 0.03 --target-top1-margin 1.0) ;;
        3) candidate_lr=2e-5; objective_args+=(--target-top1-margin-weight 0.03 --target-top1-margin 1.0) ;;
      esac
    fi
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
      --lr "$candidate_lr"
      --scope position-fc
      --loss-mode "$candidate_loss_mode"
      --draft-lm-head int4-dequant
      --draft-lm-head-group-size 128
      --draft-lm-head-scale-dtype bf16
      --seed 27
      --print-every 100
      "${objective_args[@]}"
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
      --decode-only-starts
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

# Recompute the shared checkpoint under the exact same model, corpus, draft
# head, and decode-start convention. Do not compare against a stale hard-coded
# reference when any path above is overridden.
mkdir -p "$OUT_ROOT/shared-control"
export PYTHONPATH="/home/steve/src/vllm${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
ZE_AFFINITY_MASK=0 "$PYTHON" \
  "$ROOT/scripts/evaluate-qwen27-intrinsic-mtp-offline.py" \
  --model-dir "$MODEL_DIR" \
  --dataset-dir "$FIXED_SUITE_DATASET" \
  --max-steps 3 \
  --max-starts 8192 \
  --decode-only-starts \
  --draft-lm-head int4-dequant \
  --draft-lm-head-group-size 128 \
  --draft-lm-head-scale-dtype bf16 \
  --out "$OUT_ROOT/shared-control/decode-only-mtp3-eval.json" \
  --print-every 100 \
  > "$OUT_ROOT/shared-control/decode-only-eval.log" 2>&1

"$PYTHON" - "$OUT_ROOT" "$MATRIX" "$MODEL_DIR" "$TRAIN_DATA_ROOT" \
  "$FIXED_SUITE_DATASET" "${labels[@]}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
matrix, model_dir, training_data_root, selection_dataset = sys.argv[2:6]
labels = sys.argv[6:]
control_path = root / "shared-control" / "decode-only-mtp3-eval.json"
control = json.loads(control_path.read_text())
reference = control["mean_accepted_draft_tokens"]
rows = []
for label in labels:
    path = root / label / "fixed-suite-mtp3-eval.json"
    training = root / label / "training_summary.json"
    if not path.exists():
        rows.append({"label": label, "status": "missing", "path": str(path)})
        continue
    data = json.loads(path.read_text())
    train_data = json.loads(training.read_text()) if training.exists() else {}
    accepted = data.get("mean_accepted_draft_tokens")
    rows.append({
        "label": label,
        "status": "complete",
        "starts": data.get("starts"),
        "accepted_drafts_per_start": accepted,
        "delta_vs_shared": accepted - reference if accepted is not None else None,
        "visible_tokens_per_step": data.get("mean_visible_tokens_if_k_step_spec"),
        "conditional_exact": data.get("conditional_exact"),
        "families": data.get("families"),
        "clusters": data.get("clusters"),
        "training_objectives": {
            key: train_data.get(key)
            for key in (
                "expected_prefix_survival_weight",
                "target_top1_margin_weight",
                "target_top1_margin",
                "teacher_kl_weight",
            )
        },
        "artifact": str(path),
    })
summary = {
    "classification": "diagnostic_mtp3_acceptance_objective_fixed_suite",
    "matrix": matrix,
    "valid_headline_throughput": False,
    "selection_warning": (
        "This realistic suite has been reused for prior candidate selection. "
        "It is a decode-only diagnostic selection set, not an untouched final gate."
    ),
    "model_dir": model_dir,
    "training_data_root": training_data_root,
    "selection_dataset": selection_dataset,
    "decode_only_starts": True,
    "shared_control": {
        "accepted_drafts_per_start": reference,
        "starts": control.get("starts"),
        "prompt_starts_excluded": control.get("prompt_starts_excluded"),
        "artifact": str(control_path),
    },
    "endpoint_trial_gate": {
        "minimum_delta_accepted_drafts_per_start": 0.205609,
        "reference_shared_accepted_drafts_per_start": reference,
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
