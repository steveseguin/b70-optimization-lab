#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TRAIN_ROOT="${TRAIN_ROOT:?TRAIN_ROOT must point to a completed position-FC matrix}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
MODEL_DIR="${MODEL_DIR:-/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e}"
EVAL_DATA_ROOT="${EVAL_DATA_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v6b-context-4gpu-20260707T032253Z}"
MAX_STARTS="${MAX_STARTS:-8192}"

labels=(
  allfc-allsteps-lr2e5
  freeze0-cond-lr2e5
  freeze01-cond-lr2e5
  freeze0-cond-lr1e5
)
pids=()

for gpu in 0 1 2 3; do
  label="${labels[$gpu]}"
  candidate="$TRAIN_ROOT/$label/model_extra_tensors.safetensors"
  if [[ ! -f "$candidate" ]]; then
    echo "missing candidate: $candidate" >&2
    exit 2
  fi
  (
    export ZE_AFFINITY_MASK="$gpu"
    export PYTHONPATH="/home/steve/src/vllm${PYTHONPATH:+:$PYTHONPATH}"
    export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    args=(
      "$PYTHON" "$ROOT/scripts/evaluate-qwen27-intrinsic-mtp-offline.py"
      --model-dir "$MODEL_DIR"
      --model-extra-path "$candidate"
      --max-steps 5
      --max-starts "$MAX_STARTS"
      --draft-lm-head int4-dequant
      --draft-lm-head-group-size 128
      --draft-lm-head-scale-dtype bf16
      --out "$TRAIN_ROOT/$label/unseen-v6b-eval.json"
      --print-every 100
    )
    for shard in 0 1 2 3; do
      args+=(--dataset-dir "$EVAL_DATA_ROOT/shard-$shard/dataset")
    done
    printf '%q ' "${args[@]}" > "$TRAIN_ROOT/$label/eval-command.txt"
    printf '\n' >> "$TRAIN_ROOT/$label/eval-command.txt"
    "${args[@]}" > "$TRAIN_ROOT/$label/eval.log" 2>&1
  ) &
  pids+=("$!")
done

rc=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "${labels[$i]} evaluation failed" >&2
    rc=1
  fi
done

"$PYTHON" - "$TRAIN_ROOT" "${labels[@]}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for label in sys.argv[2:]:
    path = root / label / "unseen-v6b-eval.json"
    if not path.exists():
        rows.append({"label": label, "status": "missing", "path": str(path)})
        continue
    data = json.loads(path.read_text())
    rows.append({
        "label": label,
        "status": "complete",
        "starts": data.get("starts"),
        "mean_accepted_draft_tokens": data.get("mean_accepted_draft_tokens"),
        "mean_visible_tokens_if_k_step_spec": data.get(
            "mean_visible_tokens_if_k_step_spec"
        ),
        "conditional_exact": data.get("conditional_exact"),
        "histogram": data.get("histogram_accepted_draft_tokens"),
        "families": data.get("families"),
    })
summary = {
    "classification": "diagnostic_position_specific_mtp5_unseen_corpus_eval",
    "valid_headline_throughput": False,
    "rows": rows,
}
(root / "unseen-v6b-summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(summary, indent=2, sort_keys=True))
PY

exit "$rc"
