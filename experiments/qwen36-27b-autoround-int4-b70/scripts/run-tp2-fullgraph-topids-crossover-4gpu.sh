#!/usr/bin/env bash
set -euo pipefail

# Swapped TP2 crossover: exact target top-ID verifier consumer versus the
# promoted dense-logits fullgraph transaction record.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/tp2-fullgraph-topids-crossover-$STAMP}"
CONTROL="$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
CANDIDATE="$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-topids-candidate.sh"
mkdir -p "$OUT_ROOT"

run_cell() {
  local window="$1" pair="$2" treatment="$3" port="$4"
  local runner="$CONTROL"
  [[ "$treatment" == candidate ]] && runner="$CANDIDATE"
  local label="qwen27-tp2-fullgraph-topids-${window}-${treatment}-gpu${pair//,/}"
  local cell="$OUT_ROOT/$label"
  mkdir -p "$cell"
  GPU_INDEX="$pair" ZE_AFFINITY_MASK="$pair" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1 PORT="$port" LABEL="$label" \
  RUN_DIR="$cell/run" OUT_DIR="$cell/data" RUN_QUALITY=0 \
  BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-256}" \
  "$runner" >"$cell/runner.stdout.log" 2>&1
}

run_window() {
  run_cell "$1" "$2" "$3" 19624 & local p1=$!
  run_cell "$1" "$4" "$5" 19625 & local p2=$!
  local rc=0
  wait "$p1" || rc=1
  wait "$p2" || rc=1
  return "$rc"
}

run_window window1 0,1 candidate 2,3 control
run_window window2 0,1 control 2,3 candidate

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
    "classification": "diagnostic_tp2_fullgraph_topids_swapped_four_gpu_crossover",
    "rows": rows,
    "groups": groups,
    "candidate_gain_percent": (
        (candidate / control - 1.0) * 100.0 if candidate is not None and control else None
    ),
}
(root / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT/summary.json"
