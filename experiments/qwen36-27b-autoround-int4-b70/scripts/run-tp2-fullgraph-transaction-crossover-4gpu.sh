#!/usr/bin/env bash
set -euo pipefail

# Swapped four-GPU crossover: apply the previously validated small ReplaySSM
# transaction fusions to the current 93 tok/s FP16 graph-safe full-target base.
# Diagnostic only until an isolated strict-quality confirmation wins.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/tp2-fullgraph-transaction-crossover-$STAMP}"
RUNNER="$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-capturegdn-fp16-candidate.sh"
STAGE="${STAGE:-$ROOT/experiments/qwen27_graphsafe_flash_attention/staged-package}"
CONTROL_CACHE_ROOT="${CONTROL_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/qwen27-graphsafe-fa-full-20260711T202456Z}"
CANDIDATE_CACHE_ROOT="${CANDIDATE_CACHE_ROOT:-/mnt/usb-models/llm-runtime/vllm-cache/qwen27-fullgraph-transaction-20260711}"
mkdir -p "$OUT_ROOT" "$CANDIDATE_CACHE_ROOT"

run_cell() {
  local window="$1" pair="$2" treatment="$3" port="$4"
  local fuse_pending=0 direct_out=0 cache_root="$CONTROL_CACHE_ROOT"
  if [[ "$treatment" == candidate ]]; then
    fuse_pending=1
    direct_out=1
    cache_root="$CANDIDATE_CACHE_ROOT"
  fi
  local pair_label="${pair//,/}"
  local label="qwen27-tp2-fullgraph-transaction-${window}-${treatment}-gpu${pair_label}"
  local cell="$OUT_ROOT/$label"
  mkdir -p "$cell"

  PYTHONPATH="$STAGE${PYTHONPATH:+:$PYTHONPATH}" \
  VLLM_XPU_KERNELS_SRC="$STAGE" \
  VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1 \
  VLLM_XPU_DDTREE_FULL_GRAPH=1 \
  VLLM_XPU_GDN_REPLAYSSM_FUSE_PENDING_METADATA="$fuse_pending" \
  VLLM_XPU_GDN_REPLAYSSM_DIRECT_CORE_OUT="$direct_out" \
  COMPILATION_CONFIG='{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[4],"max_cudagraph_capture_size":4}' \
  GPU_INDEX="$pair" \
  ZE_AFFINITY_MASK="$pair" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
  PORT="$port" \
  LABEL="$label" \
  RUN_DIR="$cell/run" \
  OUT_DIR="$cell/data" \
  VLLM_CACHE_ROOT="$cache_root" \
  RUN_QUALITY=0 \
  BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-256}" \
  "$RUNNER" >"$cell/runner.stdout.log" 2>&1
}

run_window() {
  local window="$1" first_pair="$2" first_treatment="$3"
  local second_pair="$4" second_treatment="$5"
  run_cell "$window" "$first_pair" "$first_treatment" 19620 &
  local p1=$!
  run_cell "$window" "$second_pair" "$second_treatment" 19621 &
  local p2=$!
  local rc=0
  wait "$p1" || rc=1
  wait "$p2" || rc=1
  return "$rc"
}

snapshot() {
  local name="$1"
  {
    date -u +%Y-%m-%dT%H:%M:%SZ
    uname -a
    for gpu in 0 1 2 3; do xpu-smi stats -d "$gpu" -j 2>/dev/null || true; done
  } >"$OUT_ROOT/$name.txt"
}

snapshot before
run_window window1 0,1 candidate 2,3 control
snapshot between
run_window window2 0,1 control 2,3 candidate
snapshot after

"${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}" - "$OUT_ROOT" <<'PY'
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted(root.glob("qwen27-tp2-*/data/*candidate-summary-*.json")):
    data = json.loads(path.read_text())
    label = data["label"]
    rows.append({
        "label": label,
        "window": "window1" if "-window1-" in label else "window2",
        "treatment": "candidate" if "-candidate-" in label else "control",
        "gpu_pair": label.rsplit("-gpu", 1)[1],
        "median_tok_s": data["primary_metric"]["median_tok_s_1_100_after_ttft"],
        "p10_tok_s": data["primary_metric"]["p10"],
        "mean_tok_s": data["primary_metric"]["mean"],
        "strict_gate": data["status"]["realistic_gate_passed"],
        "cached_tokens_all_zero": data["status"]["cached_tokens_all_zero"],
        "summary": str(path),
    })
groups = {}
for treatment in ("candidate", "control"):
    values = [r["median_tok_s"] for r in rows if r["treatment"] == treatment]
    groups[treatment] = {
        "count": len(values),
        "mean_of_medians": statistics.mean(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }
candidate = groups["candidate"]["mean_of_medians"]
control = groups["control"]["mean_of_medians"]
out = {
    "classification": "diagnostic_tp2_fullgraph_transaction_swapped_four_gpu_crossover",
    "rows": rows,
    "groups": groups,
    "candidate_gain_percent": (
        (candidate / control - 1.0) * 100.0
        if candidate is not None and control else None
    ),
    "promotion_policy": (
        "Diagnostic only; promotion requires an isolated strict suite, full "
        "quality, and a result above the current 93.036242 tok/s record."
    ),
}
(root / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT/summary.json"
