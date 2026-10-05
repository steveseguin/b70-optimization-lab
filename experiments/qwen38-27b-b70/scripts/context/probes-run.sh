#!/usr/bin/env bash
# Client for MU_MODE=serve_run (exact prefix cache on, nothing else on the server): the single-call prose-reading
# probe at two batch sizes with thinking on and off, then the edit-cost probe. Needs BASE_URL, API_BASE, MODEL_NAME, OUT_DIR.
set -u
D=$(cd "$(dirname "$0")" && pwd)
P=${PROSE_PROBE_DIR:-/mnt/fast-ai/bench-results/context-prose-probe-20261005}
T6=/mnt/fast-ai/bench-results/context-clm-fifth-20261005/client/prose120/tasks/prose-memory/prose-memory-t120k-s0
T2=$P/prose2k/prose-memory-t40k-s0
fold() { name=$1; shift; curl -sf -m 10 "$BASE_URL/health" >/dev/null || { echo "server gone before $name"; exit 3; }
         python3 "$D/prose_fold_probe.py" "$@" > "$OUT_DIR/$name.log" 2>&1; echo "== $name"; tail -n 2 "$OUT_DIR/$name.log" | cut -c1-320; }
fold probe-2k-off "$T2" --thinking off
fold probe-2k-on "$T2" --thinking on --limit 6
fold probe-6k-on "$T6" --thinking on --limit 3
bash "$D/edit-cost.sh"
