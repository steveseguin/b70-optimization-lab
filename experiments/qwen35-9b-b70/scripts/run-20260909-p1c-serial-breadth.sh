#!/usr/bin/env bash
# P1c: d3 and x32k, serially on card 0. Non-zero cards cannot host a server on this stack because
# the shared launcher sets ZE_AFFINITY_MASK and ONEAPI_DEVICE_SELECTOR from the same value and they
# compose; see 2026-09-09-launcher-confines-every-single-card-run-to-card-0.md.
set -uo pipefail
REPO=/home/steve/llm-optimizations
LOGDIR=/mnt/fast-ai/bench-results/chain-logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/q9-p1c-chain.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) P1c chain start ==="
D2=/mnt/fast-ai/bench-results/qwen35-9b-w4a16-tp1-mtp2-graph1-dhint4-20260909-d2
echo "$(date -u +%FT%TZ) waiting for d2"
until [[ -e "$D2/campaign-end.txt" || -e "$D2/ABORTED" ]]; do sleep 60; done
echo "$(date -u +%FT%TZ) d2 finished; running d3 then x32k serially on card 0"
QUEUE=$REPO/experiments/qwen35-9b-b70/data/q9-p1c-queue.tsv PARALLELISM=1 CARDS=0 SKIP_XPU_SMI=0 DISPATCH_STAGGER=30 \
  bash "$REPO/experiments/qwen35-9b-b70/scripts/q9-arm-queue-driver.sh"
echo "$(date -u +%FT%TZ) P1c driver exit $?"
echo "P1C-CHAIN-DONE"
