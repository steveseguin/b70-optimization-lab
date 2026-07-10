#!/usr/bin/env bash
set -euo pipefail

# Zero-preserving gated refinement pre-gate. Offline acceptance only.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
DATA_ROOT="${DATA_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-stacked-refinement/mtp5-gated-pre-gate-4gpu-$STAMP}"
TRAIN_STARTS="${TRAIN_STARTS:-8192}"
HELDOUT_STARTS="${HELDOUT_STARTS:-4096}"
HELDOUT_SAMPLES="${HELDOUT_SAMPLES:-16}"
BATCH_SIZE="${BATCH_SIZE:-4}"
MAX_TRAIN_STEPS="${MAX_TRAIN_STEPS:-1024}"
GPU_IDS="${GPU_IDS:-0,1,2,3}"

mkdir -p "$OUT_ROOT"
dataset_args=()
for shard in 0 1 2 3; do
  dataset_args+=(--dataset-dir "$DATA_ROOT/shard-$shard/dataset")
done

run_one() {
  local gpu="$1" label="$2" residual_mode="$3" gate_init="$4"
  local loss_mode="$5" lr="$6"
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
      --scope full
      --loss-mode "$loss_mode"
      --residual-mode "$residual_mode"
      --residual-gate-init "$gate_init"
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
all_labels=(
  vector-zero-all-lr2e-5
  vector-p01-all-lr1e-5
  vector-zero-conditional-lr2e-5
  scalar-zero-all-lr2e-5
)
if [[ ",$GPU_IDS," == *,0,* ]]; then
  run_one 0 vector-zero-all-lr2e-5 vector 0 all-steps 2e-5
fi
if [[ ",$GPU_IDS," == *,1,* ]]; then
  run_one 1 vector-p01-all-lr1e-5 vector 0.01 all-steps 1e-5
fi
if [[ ",$GPU_IDS," == *,2,* ]]; then
  run_one 2 vector-zero-conditional-lr2e-5 vector 0 conditional-prefix 2e-5
fi
if [[ ",$GPU_IDS," == *,3,* ]]; then
  run_one 3 scalar-zero-all-lr2e-5 scalar 0 all-steps 2e-5
fi
if ((${#pids[@]} == 0)); then
  echo "GPU_IDS selected no known GPU; use a comma-separated subset of 0,1,2,3" >&2
  exit 2
fi

rc=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "${labels[$i]} failed; see $OUT_ROOT/${labels[$i]}/train.log" >&2
    rc=1
  fi
done

"$PYTHON" - "$OUT_ROOT" "${all_labels[@]}" <<'PY'
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
        "residual_mode": data.get("residual_mode"),
        "residual_gate_init": data.get("residual_gate_init"),
        "loss_mode": data.get("loss_mode"),
        "lr": data.get("lr"),
        "base_only": data.get("base_only"),
        "before": data.get("before"),
        "after": data.get("after"),
        "residual_gate_after": data.get("architecture", {}).get(
            "residual_gate_after"
        ),
        "training": data.get("training"),
        "artifact": data.get("artifact"),
    })
summary = {
    "classification": "diagnostic_gated_stacked_mtp_refinement_pre_gate",
    "valid_headline_throughput": False,
    "localmaxxing_eligible": False,
    "endpoint_trial_visible_tokens_gate": 3.3,
    "headline_warning": "Offline acceptance only; not an endpoint result.",
    "rows": rows,
}
(root / "matrix-summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT"
exit "$rc"
