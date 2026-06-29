#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
MAX_TOKENS="${MAX_TOKENS:-16}"
BENCH_REPEATS="${BENCH_REPEATS:-3}"
CANARY_REPEATS="${CANARY_REPEATS:-4}"
PROMPT_MODE="${PROMPT_MODE:-filled-long-unique}"
BASE_PORT="${BASE_PORT:-18460}"

# Diagnostic ladder only. These rows are for prompt/prefill and long-context
# characterization, not LocalMaxxing short-decode record promotion.
#
# Format: GPU_INDEX:PROMPT_TOKENS:CTX_SIZE
LADDER_SPECS="${LADDER_SPECS:-0:128:2048 1:512:2048 2:2048:4096 3:4096:8192}"

echo "[gemma4-prefill-ladder] stamp=$STAMP"
echo "[gemma4-prefill-ladder] max_tokens=$MAX_TOKENS repeats=$BENCH_REPEATS prompt_mode=$PROMPT_MODE"
echo "[gemma4-prefill-ladder] specs=$LADDER_SPECS"

pids=()
labels=()

for spec in $LADDER_SPECS; do
  IFS=: read -r gpu prompt_tokens ctx_size <<<"$spec"
  if [[ -z "$gpu" || -z "$prompt_tokens" || -z "$ctx_size" ]]; then
    echo "[gemma4-prefill-ladder] invalid spec: $spec" >&2
    exit 2
  fi

  port=$((BASE_PORT + gpu))
  label="gemma4-q8-gpu${gpu}-prefill-ladder-p${prompt_tokens}-ctx${ctx_size}-o${MAX_TOKENS}-${STAMP}"
  driver_log="$ROOT/data/${label}.driver.log"
  labels+=("$label")

  echo "[gemma4-prefill-ladder] launching $label port=$port"
  (
    GPU_INDEX="$gpu" \
    PORT="$port" \
    LABEL="$label" \
    CTX_SIZE="$ctx_size" \
    PROMPT_TOKENS="$prompt_tokens" \
    BENCH_PROMPT_MODE="$PROMPT_MODE" \
    MAX_TOKENS="$MAX_TOKENS" \
    BENCH_REPEATS="$BENCH_REPEATS" \
    CANARY_REPEATS="$CANARY_REPEATS" \
    REALISTIC_GATE=0 \
    /home/steve/qwen36-results-main/repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
  ) >"$driver_log" 2>&1 &
  pids+=("$!")
done

rc=0
for i in "${!pids[@]}"; do
  pid="${pids[$i]}"
  label="${labels[$i]}"
  if wait "$pid"; then
    echo "[gemma4-prefill-ladder] PASS $label"
  else
    lane_rc=$?
    echo "[gemma4-prefill-ladder] FAIL rc=$lane_rc $label" >&2
    rc=1
  fi
done

summary="$ROOT/data/gemma4-prefill-ladder-${STAMP}.json"
python3 - "$summary" "${labels[@]}" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
labels = sys.argv[2:]
root = Path("/home/steve/qwen36-results-main")
rows = []

for label in labels:
    run_dir = root / "data" / label
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        rows.append({"label": label, "status": "missing-summary"})
        continue
    summary = json.loads(summary_path.read_text())
    bench_path = next(run_dir.glob("p*o*.json"), None)
    bench = json.loads(bench_path.read_text()) if bench_path else {}
    bsum = bench.get("summary", {})
    freshness = bench.get("fresh_response_validity", {})
    identity = (
        bench.get("bench_identity")
        or bench.get("bench_run_identity")
        or bench.get("run_identity", {})
    )
    def pick(key):
        return identity.get(key, bench.get(key, summary.get(key)))
    rows.append({
        "label": label,
        "status": "ok",
        "run_dir": str(run_dir),
        "prompt_tokens_requested": pick("prompt_tokens_requested"),
        "prompt_mode": pick("prompt_mode"),
        "max_tokens": pick("max_tokens"),
        "actual_prompt_tokens": bsum.get("prompt_tokens"),
        "ttft_s": bsum.get("ttft_s"),
        "decode_tok_s_after_ttft": bsum.get("tok_s_after_ttft"),
        "wall_tok_s": bsum.get("tok_s_wall"),
        "fresh_response_validity": freshness,
        "headline_eligible_for_gemma_q8": False,
        "localmaxxing_submission_allowed": False,
        "note": "Diagnostic prompt/prefill/context ladder only; not a short-decode promotion run.",
    })

out.write_text(json.dumps({
    "kind": "gemma4_q8_prefill_ladder",
    "policy": "diagnostic only; do not submit as LocalMaxxing headline throughput",
    "rows": rows,
}, indent=2) + "\n")
print(out)
PY

exit "$rc"
