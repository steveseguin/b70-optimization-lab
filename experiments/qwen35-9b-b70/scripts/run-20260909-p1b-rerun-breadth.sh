#!/usr/bin/env bash
# P1b: re-run the three breadth arms that died on 2026-09-09 when each arm's preflight xpu-smi ran
# while its neighbours' servers were initialising. Waits for the surviving d1 arm to finish so the
# re-run does not repeat the same four-at-once shape.
set -uo pipefail
REPO=/home/steve/llm-optimizations
LOGDIR=/mnt/fast-ai/bench-results/chain-logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/q9-p1b-chain.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) P1b chain start ==="
D1=/mnt/fast-ai/bench-results/qwen35-9b-w4a16-tp1-mtp1-graph1-dhint4-20260909-d1
echo "$(date -u +%FT%TZ) waiting for the surviving d1 arm"
until [[ -e "$D1/campaign-end.txt" || -e "$D1/ABORTED" ]]; do sleep 60; done
if [[ -e "$D1/ABORTED" ]]; then
  echo "P1b: d1 aborted: $(cat "$D1/ABORTED")"
fi
echo "$(date -u +%FT%TZ) d1 finished; re-running d2 / d3 / x32k at parallelism 3"
QUEUE=$REPO/experiments/qwen35-9b-b70/data/q9-p1b-queue.tsv PARALLELISM=3 SKIP_XPU_SMI=1 \
  bash "$REPO/experiments/qwen35-9b-b70/scripts/q9-arm-queue-driver.sh"
echo "$(date -u +%FT%TZ) P1b driver exit $?"
echo "P1B-CHAIN-DONE"
