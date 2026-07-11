#!/usr/bin/env bash
set -euo pipefail

# Two-window TP2 crossover for capturing GDN cores inside the surrounding
# PIECEWISE graph segments. Each window uses all four B70s; the second swaps
# candidate/control across the physical GPU pairs to control pair and thermal
# effects. This is diagnostic evidence, not a replacement for the isolated
# strict fresh-response and full quality gates.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/tp2-capturegdn-crossover-$STAMP}"
RUNNER="$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-oneccl-public4ce-draftgraph-candidate.sh"
CONTROL_CACHE_ROOT="${CONTROL_CACHE_ROOT:-/mnt/fast-ai/vllm-cache/qwen27-oneccl-draftgraph-customag}"
CANDIDATE_CACHE_ROOT="${CANDIDATE_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/qwen27-tp2-capturegdn-20260711}"
mkdir -p "$OUT_ROOT"

run_cell() {
  local window="$1"
  local pair="$2"
  local treatment="$3"
  local port="$4"
  local capture_gdn=0
  local cache_root="$CONTROL_CACHE_ROOT"
  if [[ "$treatment" == "candidate" ]]; then
    capture_gdn=1
    cache_root="$CANDIDATE_CACHE_ROOT"
  fi

  local pair_label="${pair//,/}"
  local label="qwen27-tp2-capturegdn-${window}-${treatment}-gpu${pair_label}"
  local cell="$OUT_ROOT/$label"
  mkdir -p "$cell"

  GPU_INDEX="$pair" \
  ZE_AFFINITY_MASK="$pair" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1 \
  PORT="$port" \
  LABEL="$label" \
  RUN_DIR="$cell/run" \
  OUT_DIR="$cell/data" \
  VLLM_CACHE_ROOT="$cache_root" \
  VLLM_XPU_DDTREE_CAPTURE_GDN_CORE="$capture_gdn" \
  RUN_QUALITY=0 \
  BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-256}" \
  "$RUNNER" >"$cell/runner.stdout.log" 2>&1
}

run_window() {
  local window="$1"
  local first_pair="$2"
  local first_treatment="$3"
  local second_pair="$4"
  local second_treatment="$5"

  run_cell "$window" "$first_pair" "$first_treatment" 19444 &
  local first_pid=$!
  run_cell "$window" "$second_pair" "$second_treatment" 19445 &
  local second_pid=$!

  local rc=0
  wait "$first_pid" || rc=1
  wait "$second_pid" || rc=1
  return "$rc"
}

snapshot_system() {
  local name="$1"
  {
    date -u +%Y-%m-%dT%H:%M:%SZ
    uname -a
    xpu-smi discovery 2>/dev/null || true
    for gpu in 0 1 2 3; do
      xpu-smi stats -d "$gpu" -j 2>/dev/null || true
    done
  } >"$OUT_ROOT/$name.txt"
}

snapshot_system before
run_window window1 0,1 candidate 2,3 control
snapshot_system between
run_window window2 0,1 control 2,3 candidate
snapshot_system after

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
    treatment = "candidate" if "-candidate-" in label else "control"
    window = "window1" if "-window1-" in label else "window2"
    pair = label.rsplit("-gpu", 1)[1]
    rows.append(
        {
            "label": label,
            "window": window,
            "treatment": treatment,
            "gpu_pair": pair,
            "median_tok_s": data["primary_metric"][
                "median_tok_s_1_100_after_ttft"
            ],
            "p10_tok_s": data["primary_metric"]["p10"],
            "mean_tok_s": data["primary_metric"]["mean"],
            "strict_gate": data["status"]["realistic_gate_passed"],
            "cached_tokens_all_zero": data["status"]["cached_tokens_all_zero"],
            "summary": str(path),
        }
    )

groups = {}
for treatment in ("candidate", "control"):
    values = [
        row["median_tok_s"]
        for row in rows
        if row["treatment"] == treatment
    ]
    groups[treatment] = {
        "count": len(values),
        "mean_of_medians": statistics.mean(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }

candidate = groups["candidate"]["mean_of_medians"]
control = groups["control"]["mean_of_medians"]
out = {
    "classification": "diagnostic_tp2_capturegdn_swapped_four_gpu_crossover",
    "rows": rows,
    "groups": groups,
    "candidate_gain_percent": (
        None
        if not candidate or not control
        else (candidate / control - 1.0) * 100.0
    ),
    "promotion_policy": (
        "Diagnostic only; promotion also requires an isolated 512-token "
        "strict suite and complete quality gate."
    ),
}
(root / "summary.json").write_text(
    json.dumps(out, indent=2, sort_keys=True) + "\n"
)
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT/summary.json"
