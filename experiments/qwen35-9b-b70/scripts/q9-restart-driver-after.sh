#!/usr/bin/env bash
# Wait for a named arm to finish, then restart the queue driver so it picks up a reordered queue.
# The driver snapshots the queue at start, so a reorder only takes effect on a restart; restarting
# at an arm boundary avoids killing work mid-flight. Completed arms are skipped on the re-run.
set -uo pipefail
REPO=/home/steve/llm-optimizations
LOGDIR=/mnt/fast-ai/bench-results/chain-logs
ARM_ROOT=${1:?set the campaign root to wait for}
exec >>"$LOGDIR/q9-restart-after.log" 2>&1
echo "=== $(date -u +%FT%TZ) waiting for $(basename "$ARM_ROOT") ==="
until [[ -e "$ARM_ROOT/campaign-end.txt" || -e "$ARM_ROOT/ABORTED" ]]; do sleep 30; done
echo "$(date -u +%FT%TZ) arm finished; stopping the driver"
# Bracket idiom so this script's own command line cannot match the pattern.
# Kill the driver AND its harness children. Killing only the wrapper leaves the child running: it
# relaunches its container while the docker stop below is trying to remove it, and the two fight.
# Third occurrence of this trap in one session - a queued wrapper that has passed its wait loop has
# already spawned its campaign, so the child must be named explicitly.
pids=$(ps -eo pid,args | grep -E '[q]9-arm-queue-driver|[c]ampaign-v3-' | awk '{print $1}')
[[ -n "$pids" ]] && kill -TERM $pids 2>/dev/null
sleep 20
# Anything that respawned in the meantime.
pids=$(ps -eo pid,args | grep -E '[q]9-arm-queue-driver|[c]ampaign-v3-' | awk '{print $1}')
[[ -n "$pids" ]] && kill -KILL $pids 2>/dev/null
# An arm killed mid-flight leaves a partial campaign root, which the driver's skip check would treat
# as completed. Archive it so the arm re-runs instead of silently vanishing from the campaign.
for d in $(ls -d /mnt/fast-ai/bench-results/qwen35-9b-w4a16-*-20260909-* 2>/dev/null); do
  case "$d" in *failed*|*invalid*|*aborted*|*killed*) continue;; esac
  [[ -e "$d/campaign-end.txt" || -e "$d/ABORTED" ]] && continue
  echo "$(date -u +%FT%TZ) archiving partial root $(basename "$d")"
  mv "$d" "${d}-killed-at-restart-boundary" 2>/dev/null || true
done
for c in $(docker ps --format '{{.Names}}' | grep '^qwen35' || true); do docker stop -t 120 "$c" >/dev/null 2>&1; done
echo "$(date -u +%FT%TZ) restarting the driver with the reordered queue"
PARALLELISM=1 CARDS=0 SKIP_XPU_SMI=0 DISPATCH_STAGGER=30 \
  nohup bash "$REPO/experiments/qwen35-9b-b70/scripts/q9-arm-queue-driver.sh" >/dev/null 2>&1 &
echo "$(date -u +%FT%TZ) driver restarted pid=$!"
echo "Q9-RESTART-DONE"
