#!/usr/bin/env bash
# The target-head-split-2026-10-29 suite: three arms in this fixed order (two-card control, four-card TP, four-card TP with
# the rank-1 target head split), each run once as its own transient runner unit (run_arm.sh) while sc117-tp-svc-th-locks-20261029
# holds all four card locks. A failed or halted arm ends the chain (nothing is retried). Then the lock holder stops.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/target-head-split-2026-10-29
R=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/receipts/b7786ad42675.json
exec >>"$D/logs/suite-chain.log" 2>&1
echo "=== chain start $(date -Is)"
for arm in two tp tpt; do
  [ "$(systemctl --user is-active sc117-tp-svc-th-locks-20261029)" = active ] || { echo "lock holder not active before $arm"; break; }
  echo "--- arm $arm start $(date -Is)"
  systemd-run --user --unit=sc117-tp-svc-th-run-$arm-20261029 -p Restart=no --wait --collect -E SC117_ENGINE_RECEIPT=$R bash $D/run_arm.sh $arm
  st=$(cat "$D/logs/STATUS-$arm" 2>/dev/null); echo "arm $arm: $st at $(date -Is)"
  [ "$st" = "done $arm" ] || { echo "HALT chain after $arm"; break; }
done
systemctl --user stop sc117-tp-svc-th-locks-20261029
echo "=== chain end $(date -Is)"
