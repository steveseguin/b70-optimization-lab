#!/usr/bin/env bash
# LongMemEval retention study, stage 1 (prereg notes/2026-10-07-longmemeval-retention-prereg.md):
#   F on all 56 questions (in-window one-call control), then the 7-question pilot for B32ira-free, C32, E32r.
# Ar (keep everything, 262K window) runs on its own server later. Run by the campaign's serve_run mode, which
# sets API_BASE, BASE_URL, MODEL_NAME and OUT_DIR. `touch $OUT_DIR/STOP` ends it between trials.
cd /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context || exit 2
export OUT_DIR=/mnt/fast-ai/bench-results/context-longmemeval-20261007/campaign/client TASKS_ROOT=/mnt/fast-ai/datasets/longmemeval/tasks-s8-seed0
rm -f "$OUT_DIR/STOP"   # stage 1b continues the stage-1 client dir (F finished there; finished jobs are skipped)
run() { [ -e "$OUT_DIR/STOP" ] && { echo "### stopped by STOP"; exit 0; }; echo "### [$1] $(date +%H:%M)"; bash ./longmemeval-run.sh "$1" || echo "### $1 ended rc=$?"
        curl -sf -m 10 "$BASE_URL/health" >/dev/null || { echo "### server gone"; exit 3; }; }
run F
PILOT=1 run B32ira-free
PILOT=1 run C32
PILOT=1 run E32r
echo "### stage 1 complete $(date +%H:%M)"
