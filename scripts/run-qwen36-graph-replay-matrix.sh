#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/steve/llm-optimizations}"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
PYTHON="${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}"
STAMP="${STAMP:-$(date -u +%Y%m%d%H%M%S)}"
MATRIX_LABEL="${MATRIX_LABEL:-qwen36-graph-replay-matrix}"
SUMMARY_OUT="${SUMMARY_OUT:-$DATA_DIR/$MATRIX_LABEL-summary-$STAMP.json}"
JSON_REPEATS="${JSON_REPEATS:-64}"
COLOR_REPEATS="${COLOR_REPEATS:-64}"
METRICS_REPEATS="${METRICS_REPEATS:-1}"

mkdir -p "$DATA_DIR"

run_variant() {
  local label="$1"
  shift
  echo "[replay-matrix] variant=$label"
  (
    export STAMP="${STAMP}-${label}"
    export METRICS_REPEATS
    export JSON_REPEATS
    export COLOR_REPEATS
    export GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.90}"
    export COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
    export XPU_GRAPH=1
    export VLLM_XPU_ENABLE_XPU_GRAPH=1
    export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-0}"
    export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-1}"
    export VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY="${VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY:-1}"
    export VLLM_XPU_CUDAGRAPH_REPLAY_MAX_PIECEWISE_INDEX="${VLLM_XPU_CUDAGRAPH_REPLAY_MAX_PIECEWISE_INDEX:-0}"
    for override in "$@"; do
      case "$override" in
        unset:*)
          unset "${override#unset:}"
          ;;
        *=*)
          export "$override"
          ;;
        *)
          echo "[replay-matrix] invalid override for $label: $override" >&2
          exit 2
          ;;
      esac
    done
    "$ROOT/scripts/run-qwen36-ablation-candidate.sh" "$label"
  )
}

variants=()

run_variant "piecewise-prefix0-control" \
  unset:VLLM_XPU_SYNC_CUDAGRAPH_REPLAY \
  unset:VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX \
  unset:VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_RETURN_DIRECT \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES
variants+=("piecewise-prefix0-control")

run_variant "piecewise-prefix0-sync" \
  VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1 \
  unset:VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX \
  unset:VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_RETURN_DIRECT \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES
variants+=("piecewise-prefix0-sync")

run_variant "piecewise-prefix0-compare" \
  VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX='piecewise:0/' \
  VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_MAX_LINES="${COMPARE_DIRECT_MAX_LINES:-64}" \
  VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_FILE="$DATA_DIR/qwen36-replay-matrix-compare-$STAMP-r{rank}.jsonl" \
  VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_MAX_LINES="${REPLAY_TRACE_MAX_LINES:-512}" \
  VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_DIGEST=1 \
  unset:VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_RETURN_DIRECT \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES
variants+=("piecewise-prefix0-compare")

run_variant "piecewise-prefix0-return-direct" \
  VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_REGEX='piecewise:0/' \
  VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_RETURN_DIRECT=1 \
  VLLM_XPU_CUDAGRAPH_COMPARE_DIRECT_MAX_LINES="${COMPARE_DIRECT_MAX_LINES:-64}" \
  VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_FILE="$DATA_DIR/qwen36-replay-matrix-return-direct-$STAMP-r{rank}.jsonl" \
  VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_MAX_LINES="${REPLAY_TRACE_MAX_LINES:-512}" \
  VLLM_XPU_CUDAGRAPH_REPLAY_TRACE_DIGEST=1 \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_REGEX \
  unset:VLLM_XPU_CUDAGRAPH_ZERO_REPLAY_OUTPUT_INDICES
variants+=("piecewise-prefix0-return-direct")

"$PYTHON" - "$SUMMARY_OUT" "$DATA_DIR" "$STAMP" "${variants[@]}" <<'PY'
import glob
import json
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
data_dir = Path(sys.argv[2])
stamp = sys.argv[3]
variants = sys.argv[4:]

records = []
for variant in variants:
    pattern = str(data_dir / f"qwen36-ablation-{variant}-summary-{stamp}-{variant}.json")
    matches = sorted(glob.glob(pattern))
    if not matches:
        matches = sorted(glob.glob(str(data_dir / f"qwen36-ablation-{variant}-summary-*.json")))
    latest = matches[-1] if matches else None
    record = {"variant": variant, "summary": latest}
    if latest:
        try:
            data = json.loads(Path(latest).read_text(encoding="utf-8"))
            record["return_codes"] = data.get("return_codes")
            record["json_canary"] = data.get("json_canary")
            record["color_canary"] = data.get("color_canary")
            record["metrics_summary"] = data.get("metrics_summary")
            record["artifacts"] = data.get("artifacts")
        except Exception as exc:
            record["error"] = repr(exc)
    records.append(record)

payload = {
    "stamp": stamp,
    "purpose": "Qwen3.6 piecewise decode graph replay correctness matrix",
    "warning": "Any semantic canary failure rejects the graph variant regardless of speed.",
    "variants": records,
}
out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"summary": str(out_path)}, sort_keys=True))
PY

echo "[replay-matrix] summary=$SUMMARY_OUT"
