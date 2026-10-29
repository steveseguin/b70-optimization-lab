#!/usr/bin/env bash
# The research/tp/rank0-trims-2026-10-29 suite: four fresh lab-service launches on one binary in this fixed A/B/A/B order,
# the current four-card service flags (tpts) against them plus the rank-0 trims (tptsx): tpts-r1, tptsx-r1, tpts-r2,
# tptsx-r2, each once (run_arm_suite.sh), while sc117-tp-svc-r0t-locks-20261029 holds all four card locks. A failed or
# halted server ends the run (nothing is retried). Then the lock holder stops. Usage: suite.sh RECEIPT.json
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/rank0-trims-2026-10-29
R=$1; [ -f "$R" ] || { echo "no receipt $R"; exit 1; }
exec >>"$D/logs/suite.log" 2>&1
echo "=== repeat start $(date -Is)"
systemd-run --user --unit=sc117-tp-svc-r0t-locks-20261029 -p Restart=no flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card27.lock \
  flock -n -E 75 /dev/shm/card43.lock flock -n -E 75 /dev/shm/card47.lock sleep 14400 || { echo "lock holder failed"; exit 1; }
sleep 2
for name in tpts-r1 tptsx-r1 tpts-r2 tptsx-r2; do
  [ "$(systemctl --user is-active sc117-tp-svc-r0t-locks-20261029)" = active ] || { echo "lock holder not active before $name"; break; }
  echo "--- server $name start $(date -Is)"
  systemd-run --user --unit=sc117-tp-svc-r0t-run-$name-20261029 -p Restart=no --wait --collect -E SC117_ENGINE_RECEIPT=$R bash $D/run_arm_suite.sh $name
  st=$(cat "$D/logs/STATUS-$name" 2>/dev/null); echo "server $name: $st at $(date -Is)"
  [ "$st" = "done $name" ] || { echo "HALT repeat after $name"; break; }
done
systemctl --user stop sc117-tp-svc-r0t-locks-20261029
echo "=== repeat end $(date -Is)"
