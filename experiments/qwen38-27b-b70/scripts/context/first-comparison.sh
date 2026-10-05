#!/usr/bin/env bash
# First self-editing comparison on the key-value stream task (a re-creation of the paper's KV Store task).
# Run by the campaign's serve_run mode, which sets API_BASE, MODEL_NAME and OUT_DIR.
#   arms at a 32,768-token budget: self-editing (CLM), summary at 75 %, no management
#   then no management with no budget on the same server (needs a window that holds the whole task)
# notes/2026-10-05-context-window-prereg.md
set -uo pipefail
D=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
O=${OUT_DIR:?}
export PRESSURES="${PRESSURES:-1 2 4}" SEEDS="${SEEDS:-0}"
echo "== smoke"; CONTEXT_BUDGET=28672 MAX_TOKENS=4096 "$D/smoke.sh" "$O/smoke" || { echo "smoke failed"; exit 1; }
echo "== 32K budget: self-editing"; CONTEXT_BUDGET=32768 MAX_TOKENS=8192 "$D/run-contextbench-clm.sh" "$O/kv32k"
echo "== 32K budget: summary and plain"; CONTEXT_BUDGET=32768 MAX_TOKENS=8192 BASELINE=both "$D/run-contextbench-baseline.sh" "$O/kv32k"
echo "== no budget (whole task in the window): plain"; mkdir -p "$O/kvbig"; cp -r "$O/kv32k/tasks" "$O/kvbig/tasks" 2>/dev/null
CONTEXT_BUDGET=0 MAX_TOKENS=8192 BASELINE=plain "$D/run-contextbench-baseline.sh" "$O/kvbig"
"$D/summarize_results.py" "$O"/kv32k/jobs/* "$O"/kvbig/jobs/* 2>&1 | tee "$O/summary.txt"
