#!/usr/bin/env bash
# P2: run the lever queue after the breadth phase finishes. Four arms at a time; every arm is an
# identity gate first and a screening rate second, because three neighbours hold cards throughout.
# Winners are re-run serially on a quiet host before any of their rates becomes a verdict.
set -uo pipefail
REPO=/home/steve/llm-optimizations
LOGDIR=/mnt/fast-ai/bench-results/chain-logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/q9-p2-chain.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) P2 chain start ==="
echo "$(date -u +%FT%TZ) waiting for P1"
until grep -q P1-CHAIN-DONE "$LOGDIR/q9-p1-chain.log" 2>/dev/null; do sleep 60; done
echo "$(date -u +%FT%TZ) P1 finished; starting the lever queue at parallelism 4"
PARALLELISM=4 bash "$REPO/experiments/qwen35-9b-b70/scripts/q9-arm-queue-driver.sh"
echo "$(date -u +%FT%TZ) queue driver exit $?"
echo "P2-CHAIN-DONE"
