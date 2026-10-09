#!/usr/bin/env bash
# LongMemEval retention study, stage 2 RESUME (after the 09:27 memory-guard stop): the deciding pair on all 56 questions, fresh trials (pilot results are
# development data and are not pooled: new client dir). F's 56 control trials are copied in (skipped, kept in the tables).
cd /home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/context || exit 2
export OUT_DIR=/mnt/fast-ai/bench-results/context-longmemeval-20261007/stage2-client TASKS_ROOT=/mnt/fast-ai/datasets/longmemeval/tasks-s8-seed0
rm -f "$OUT_DIR/STOP"
run() { [ -e "$OUT_DIR/STOP" ] && { echo "### stopped by STOP"; exit 0; }; echo "### [$1] $(date +%H:%M)"; bash ./longmemeval-run.sh "$1" || echo "### $1 ended rc=$?"
        curl -sf -m 10 "$BASE_URL/health" >/dev/null || { echo "### server gone"; exit 3; }; }
run B32ira-free
run C32
echo "### [judge stage 2] $(date +%H:%M)"; python3 ./longmemeval_judge.py $OUT_DIR/runs/jobs/* --out /mnt/fast-ai/bench-results/context-longmemeval-20261007/verdicts-stage2-local.jsonl --local || echo "### judge stage 2 rc=$?"
python3 ./longmemeval_summary.py $OUT_DIR/runs/jobs --verdicts /mnt/fast-ai/bench-results/context-longmemeval-20261007/verdicts-stage2-local.jsonl > /mnt/fast-ai/bench-results/context-longmemeval-20261007/summary-stage2-judged-local.txt 2>&1 || echo "### summary rc=$?"
echo "### stage 2 complete $(date +%H:%M)"
