#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${MODEL:?MODEL must point to a GGUF file}"
MODEL_ALIAS="${MODEL_ALIAS:-rapid-llamacpp-model}"
BASE_LABEL="${BASE_LABEL:-${MODEL_ALIAS}-llamacpp-faon-cacheoff-screen}"
PORT_BASE="${PORT_BASE:-19670}"
MAX_TOKENS="${MAX_TOKENS:-128}"
METRIC_TOKENS="${METRIC_TOKENS:-100}"
FLASH_ATTN="${FLASH_ATTN:-on}"
CACHE_TYPE_K="${CACHE_TYPE_K:-f16}"
CACHE_TYPE_V="${CACHE_TYPE_V:-f16}"
OUT_DIR="${OUT_DIR:-$ROOT/data/rapid-model-snapshots-b70}"

# Format: suffix|ctx|batch|ubatch|poll|extra_llama_args
# Keep cache disabled in every default variant so screen rows are eligible as
# strict evidence if the final gate passes.
VARIANTS="${VARIANTS:-default-ctx4096|4096|1024|256|50|--cache-ram 0
poll100-ctx4096|4096|1024|256|100|--cache-ram 0
ctx2048|2048|1024|256|50|--cache-ram 0
ub512-ctx4096|4096|1024|512|50|--cache-ram 0}"

cd "$ROOT"
mkdir -p "$OUT_DIR"

pids=()
labels=()
gpu=0
while IFS='|' read -r suffix ctx batch ubatch poll extra_args; do
  [[ -n "${suffix:-}" ]] || continue
  if (( gpu > 3 )); then
    echo "Only four B70 GPUs are available; ignoring extra variant: $suffix" >&2
    continue
  fi
  port=$((PORT_BASE + gpu))
  label="${BASE_LABEL}-${suffix}"
  labels+=("$label")
  (
    MODEL="$MODEL" \
    MODEL_ALIAS="$MODEL_ALIAS" \
    LABEL="$label" \
    GPU_INDEX="$gpu" \
    PORT="$port" \
    CTX_SIZE="$ctx" \
    BATCH_SIZE="$batch" \
    UBATCH_SIZE="$ubatch" \
    POLL="$poll" \
    FLASH_ATTN="$FLASH_ATTN" \
    CACHE_TYPE_K="$CACHE_TYPE_K" \
    CACHE_TYPE_V="$CACHE_TYPE_V" \
    EXTRA_LLAMA_ARGS="$extra_args" \
    MAX_TOKENS="$MAX_TOKENS" \
    METRIC_TOKENS="$METRIC_TOKENS" \
    OUT_DIR="$OUT_DIR" \
      scripts/run-rapid-llamacpp-realistic-candidate.sh
  ) >"$OUT_DIR/${label}.screen.log" 2>&1 &
  pids+=("$!")
  echo "started gpu=$gpu port=$port label=$label"
  gpu=$((gpu + 1))
done <<< "$VARIANTS"

rc=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "variant failed: ${labels[$i]} (see $OUT_DIR/${labels[$i]}.screen.log)" >&2
    rc=1
  fi
done

python3 - "$OUT_DIR" "${labels[@]}" <<'PY'
import glob
import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
labels = sys.argv[2:]
rows = []
for label in labels:
    matches = sorted(glob.glob(str(out_dir / f"{label}-*.json")))
    if not matches:
        rows.append((label, "missing", None, None, None, None))
        continue
    path = matches[-1]
    with open(path) as f:
        data = json.load(f)
    gate = data.get("realistic_final_gate", {})
    metric = data.get("summary", {}).get("tok_s_1_100_after_ttft", {})
    ttft = data.get("summary", {}).get("ttft_ms", {})
    rows.append((
        label,
        "pass" if gate.get("passed") else "fail",
        metric.get("median"),
        metric.get("p10"),
        metric.get("mean"),
        ttft.get("median"),
        path,
    ))

print("| Label | Gate | Median tok/s | p10 | mean | TTFT ms | Evidence |")
print("| --- | --- | ---: | ---: | ---: | ---: | --- |")
for row in rows:
    label, gate, median, p10, mean, ttft, path = row
    print(
        f"| `{label}` | {gate} | {median} | {p10} | {mean} | {ttft} | `{path}` |"
    )
PY

exit "$rc"
