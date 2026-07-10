#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/local/qwen27-position-adapter-rank512-mtp5-20260709}"
DATA_ROOT="${DATA_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6-chat-4gpu-20260707T012928Z}"
STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/usb-models/llm-optimization-artifacts/qwen27-position-adapter/mtp5-rank512-continuation-$STAMP}"
TRAIN_STARTS="${TRAIN_STARTS:-65536}"
HELDOUT_STARTS="${HELDOUT_STARTS:-8192}"
HELDOUT_SAMPLES="${HELDOUT_SAMPLES:-288}"
BATCH_SIZE="${BATCH_SIZE:-4}"

mkdir -p "$OUT_ROOT"
dataset_args=()
for shard in 0 1 2 3; do
  dataset_args+=(--dataset-dir "$DATA_ROOT/shard-$shard/dataset")
done

run_one() {
  local gpu="$1"
  local lr="$2"
  local label="rank512-resume-lr${lr//./p}"
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
      --epochs 1
      --lr "$lr"
      --weight-decay 0
      --scope position-adapter
      --position-adapter-rank 512
      --resume-position-adapters
      --loss-mode all-steps
      --draft-lm-head int4-dequant
      --draft-lm-head-group-size 128
      --draft-lm-head-scale-dtype bf16
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
run_one 0 7e-5
run_one 1 1.4e-4
run_one 2 2.8e-4
run_one 3 5.6e-4

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
        "rank": data.get("position_adapter_rank"),
        "lr": data.get("lr"),
        "initialization": data.get("position_adapter_initialization"),
        "before": data.get("before"),
        "after": data.get("after"),
        "elapsed_s": data.get("elapsed_s"),
        "model_extra": str(root / label / "model_extra_tensors.safetensors"),
    })
summary = {
    "classification": "diagnostic_position_adapter_rank512_continuation",
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
