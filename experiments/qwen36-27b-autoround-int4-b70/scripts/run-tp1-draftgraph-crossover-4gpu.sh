#!/usr/bin/env bash
set -euo pipefail

# Diagnostic two-window crossover for the TP1 intrinsic-MTP draft graph.
# Window A: graph on GPUs 0/1, eager draft on GPUs 2/3. Window B swaps the
# treatments. This controls for per-GPU and thermal differences. It does not
# replace the isolated full strict + quality gate required for promotion.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_ROOT="${OUT_ROOT:-/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/tp1-draftgraph-crossover-$STAMP}"
RUNNER="$ROOT/experiments/qwen36-27b-autoround-int4-b70/scripts/run-tp1-current-candidate.sh"
CACHE_ROOT="${CACHE_ROOT:-/mnt/fast-ai/vllm-cache/qwen27-tp1-crossover-$STAMP}"
INDUCTOR_ROOT="${INDUCTOR_ROOT:-/mnt/fast-ai/torchinductor-cache/qwen27-tp1-crossover-$STAMP}"
KEEP_COMPILE_CACHES="${KEEP_COMPILE_CACHES:-0}"
mkdir -p "$OUT_ROOT"

cleanup_caches() {
  if [[ "$KEEP_COMPILE_CACHES" == "0" ]]; then
    local path
    for path in "$CACHE_ROOT" "$INDUCTOR_ROOT"; do
      case "$path" in
        ""|/|/home|/mnt|/mnt/fast-ai)
          echo "Refusing unsafe compile-cache cleanup path: $path" >&2
          ;;
        *)
          rm -rf -- "$path"
          ;;
      esac
    done
  fi
}
trap cleanup_caches EXIT

run_cell() {
  local window="$1"
  local gpu="$2"
  local graph="$3"
  local port="$4"
  local mode="eager"
  if [[ "$graph" == "0" ]]; then
    mode="graph"
  fi
  local label="qwen27-tp1-${mode}-${window}-gpu${gpu}"
  local cell="$OUT_ROOT/$label"
  mkdir -p "$cell"

  GPU_INDEX="$gpu" \
  ZE_AFFINITY_MASK="$gpu" \
  ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  PORT="$port" \
  LABEL="$label" \
  RUN_DIR="$cell/run" \
  OUT_DIR="$cell/data" \
  VLLM_CACHE_ROOT="$CACHE_ROOT/gpu${gpu}" \
  TORCHINDUCTOR_CACHE_DIR="$INDUCTOR_ROOT/gpu${gpu}" \
  VLLM_XPU_DRAFT_DISABLE_CUDAGRAPHS="$graph" \
  RUN_QUALITY=0 \
  BENCH_MAX_TOKENS="${BENCH_MAX_TOKENS:-256}" \
  "$RUNNER" > "$cell/runner.stdout.log" 2>&1
}

run_window() {
  local window="$1"
  shift
  local pids=()
  local spec gpu graph port
  for spec in "$@"; do
    IFS=: read -r gpu graph port <<< "$spec"
    run_cell "$window" "$gpu" "$graph" "$port" &
    pids+=("$!")
  done
  local rc=0
  local pid
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
      rc=1
    fi
  done
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
  } > "$OUT_ROOT/$name.txt"
}

snapshot_system before
run_window window1 0:0:19440 1:0:19441 2:1:19442 3:1:19443
snapshot_system between
run_window window2 0:1:19444 1:1:19445 2:0:19446 3:0:19447
snapshot_system after

"${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}" - "$OUT_ROOT" <<'PY'
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted(root.glob("qwen27-tp1-*/data/*candidate-summary-*.json")):
    data = json.loads(path.read_text())
    label = data["label"]
    mode = "graph" if "-graph-" in label else "eager"
    gpu = int(label.rsplit("gpu", 1)[1])
    rows.append({
        "label": label,
        "mode": mode,
        "gpu": gpu,
        "median_tok_s": data["primary_metric"]["median_tok_s_1_100_after_ttft"],
        "p10_tok_s": data["primary_metric"]["p10"],
        "mean_tok_s": data["primary_metric"]["mean"],
        "strict_gate": data["status"]["realistic_gate_passed"],
        "cached_tokens_all_zero": data["status"]["cached_tokens_all_zero"],
        "summary": str(path),
    })

grouped = {}
for mode in ("graph", "eager"):
    values = [row["median_tok_s"] for row in rows if row["mode"] == mode]
    grouped[mode] = {
        "count": len(values),
        "mean_of_medians": statistics.mean(values) if values else None,
        "median_of_medians": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }

graph = grouped["graph"]["mean_of_medians"]
eager = grouped["eager"]["mean_of_medians"]
out = {
    "classification": "diagnostic_tp1_draftgraph_swapped_four_gpu_crossover",
    "rows": rows,
    "groups": grouped,
    "graph_gain_percent": None if not graph or not eager else (graph / eager - 1.0) * 100.0,
    "promotion_policy": "Diagnostic only; any win needs an isolated 512-token strict suite and full quality gate.",
}
(root / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(json.dumps(out, indent=2, sort_keys=True))
PY

echo "$OUT_ROOT/summary.json"
