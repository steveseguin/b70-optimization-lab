#!/usr/bin/env bash
# The target-head-split-2026-10-29 fresh-server repeat: four lab-service launches on binary b7786ad42675 in this fixed order,
# alternating TP and TP with both head splits (tp-r1, tpts-r1, tp-r2, tpts-r2), each once (run_arm_repeat.sh), while
# sc117-tp-svc-th-rep-locks-20261029 holds all four card locks. A failed or halted server ends the run (nothing is
# retried). Then the lock holder stops.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/target-head-split-2026-10-29
R=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/receipts/b7786ad42675.json
exec >>"$D/logs/suite-repeat.log" 2>&1
echo "=== repeat start $(date -Is)"
systemd-run --user --unit=sc117-tp-svc-th-rep-locks-20261029 -p Restart=no flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card27.lock \
  flock -n -E 75 /dev/shm/card43.lock flock -n -E 75 /dev/shm/card47.lock sleep 14400 || { echo "lock holder failed"; exit 1; }
sleep 2
for name in tp-r1 tpts-r1 tp-r2 tpts-r2; do
  [ "$(systemctl --user is-active sc117-tp-svc-th-rep-locks-20261029)" = active ] || { echo "lock holder not active before $name"; break; }
  echo "--- server $name start $(date -Is)"
  systemd-run --user --unit=sc117-tp-svc-th-rep-run-$name-20261029 -p Restart=no --wait --collect -E SC117_ENGINE_RECEIPT=$R bash $D/run_arm_repeat.sh $name
  st=$(cat "$D/logs/STATUS-$name" 2>/dev/null); echo "server $name: $st at $(date -Is)"
  [ "$st" = "done $name" ] || { echo "HALT repeat after $name"; break; }
done
systemctl --user stop sc117-tp-svc-th-rep-locks-20261029
echo "=== repeat end $(date -Is)"
