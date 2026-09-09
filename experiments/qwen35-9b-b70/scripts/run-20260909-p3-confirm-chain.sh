#!/usr/bin/env bash
# P3: re-run the arms that survived P2 serially on a quiet host, so their rates become verdicts
# rather than screens. Parallelism 1 by construction - a timed row never shares the host.
set -uo pipefail
REPO=/home/steve/llm-optimizations
LOGDIR=/mnt/fast-ai/bench-results/chain-logs; mkdir -p "$LOGDIR"
LOG=$LOGDIR/q9-p3-chain.log
exec >>"$LOG" 2>&1
echo "=== $(date -u +%FT%TZ) P3 chain start ==="
echo "$(date -u +%FT%TZ) waiting for the lever queue"
until grep -q "Q9-QUEUE-DONE" "$LOGDIR/q9-queue-driver.log" 2>/dev/null; do sleep 60; done

Q=$REPO/experiments/qwen35-9b-b70/data/q9-p3-confirm-queue.tsv
echo "$(date -u +%FT%TZ) selecting confirm arms"
python3 "$REPO/experiments/qwen35-9b-b70/scripts/q9-select-confirm-arms.py" --baseline-run p0 --out "$Q"
rc=$?
if [[ $rc -ne 0 ]]; then
  echo "P3-ABORT: could not select confirm arms (rc=$rc)"; echo "P3-CHAIN-DONE"; exit 2
fi
n=$(awk -F'\t' '!/^#/ && NF>1' "$Q" 2>/dev/null | wc -l)
if [[ "$n" -eq 0 ]]; then
  echo "P3: no arm beat the baseline while staying lossless; nothing to confirm"
  echo "P3-CHAIN-DONE"; exit 0
fi
echo "$(date -u +%FT%TZ) confirming $n arms serially on a quiet host"
QUEUE="$Q" PARALLELISM=1 bash "$REPO/experiments/qwen35-9b-b70/scripts/q9-arm-queue-driver.sh"
echo "$(date -u +%FT%TZ) confirm driver exit $?"
echo "P3-CHAIN-DONE"
