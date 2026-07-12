#!/usr/bin/env bash
set -euo pipefail

# Swapped TP2 crossover for a disclosed, in-spec 2.8 GHz core-frequency lock.
# The 230 W firmware power cap is unchanged. All cards are restored to the
# default 400-2800 MHz range on every exit path.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/tp2-frequency-lock-crossover-$STAMP}"
RUNNER="$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp2-fullgraph-transaction-candidate.sh"
SUDO_PASSWORD_FILE="${SUDO_PASSWORD_FILE:-/home/steve/SUDOPASSWORD.txt}"
mkdir -p "$OUT_ROOT"

sudo_xpu() {
  local password
  password="$(< "$SUDO_PASSWORD_FILE")"
  printf '%s\n' "$password" | sudo -S xpu-smi "$@" >/dev/null 2>&1
}

set_range() {
  local gpu="$1" min="$2" max="$3"
  sudo_xpu config -d "$gpu" -t 0 --frequencyrange "$min,$max"
}

restore_all() {
  local gpu
  for gpu in 0 1 2 3; do
    set_range "$gpu" 400 2800 || true
  done
}
trap restore_all EXIT INT TERM

snapshot() {
  local name="$1" gpu
  {
    date -u +%Y-%m-%dT%H:%M:%SZ
    for gpu in 0 1 2 3; do
      echo "=== GPU $gpu config ==="
      xpu-smi config -d "$gpu" -j
      echo "=== GPU $gpu stats ==="
      xpu-smi stats -d "$gpu" -j || true
    done
  } >"$OUT_ROOT/$name.txt"
}

run_cell() {
  local window="$1" pair="$2" treatment="$3" port="$4"
  local label="qwen27-tp2-frequency-${window}-${treatment}-gpu${pair//,/}"
  local cell="$OUT_ROOT/$label"
  mkdir -p "$cell"
  GPU_INDEX="$pair" ZE_AFFINITY_MASK="$pair" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1 PORT="$port" LABEL="$label" \
  RUN_DIR="$cell/run" OUT_DIR="$cell/data" RUN_QUALITY=0 \
  BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-256}" \
  "$RUNNER" >"$cell/runner.stdout.log" 2>&1
}

run_window() {
  local window="$1" locked_pair="$2" control_pair="$3"
  restore_all
  IFS=, read -r locked_a locked_b <<<"$locked_pair"
  set_range "$locked_a" 2800 2800
  set_range "$locked_b" 2800 2800
  snapshot "${window}-before"
  run_cell "$window" "$locked_pair" candidate 19626 & local p1=$!
  run_cell "$window" "$control_pair" control 19627 & local p2=$!
  local rc=0
  wait "$p1" || rc=1
  wait "$p2" || rc=1
  snapshot "${window}-after"
  return "$rc"
}

run_window window1 0,1 2,3
run_window window2 2,3 0,1
restore_all

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
    "classification": "diagnostic_tp2_2800mhz_swapped_four_gpu_crossover",
    "power_cap_w": 230,
    "candidate_frequency_mhz": [2800, 2800],
    "control_frequency_mhz": [400, 2800],
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
