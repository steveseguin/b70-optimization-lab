#!/usr/bin/env bash
# Copy of ctx131072-2026-10-29/suite.sh for research/tp/prefill-host-2026-10-30 (paths and unit names only). The lab-service chain: fresh lab-service launches, in the given order, each once
# (run_arm_suite.sh), while sc117-tp-svc-pfh-locks-20261030 holds all four card locks. A failed or halted server ends the
# chain (nothing is retried). Then the lock holder stops. Usage: suite.sh RECEIPT.json NAME:CTX[:record] ...
# (NAME = <arm>-r<N> of arm_env.py; CTX 65536 or 131072; record = ARM_RECORD_ORACLE=1 for the first 131072 server.)
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-host-2026-10-30
R=$1; shift; [ -f "$R" ] || { echo "no receipt $R"; exit 1; }
exec >>"$D/logs/suite.log" 2>&1
echo "=== chain start $(date -Is): $*"
# prefill-host-2026-10-30: the holder waits (bounded, 1 h per lock) for a card another agent holds, and the chain starts
# only once every lock is held by a process of the holder unit's own cgroup.
systemd-run --user --unit=sc117-tp-svc-pfh-locks-20261030 -p Restart=no flock -w 3600 -E 75 /dev/shm/card23.lock flock -w 3600 -E 75 /dev/shm/card27.lock \
  flock -w 3600 -E 75 /dev/shm/card43.lock flock -w 3600 -E 75 /dev/shm/card47.lock sleep 28800 || { echo "lock holder failed"; exit 1; }
held=0
for i in $(seq 1 1500); do
  sleep 5
  [ "$(systemctl --user is-active sc117-tp-svc-pfh-locks-20261030)" = active ] || break
  cg=$(systemctl --user show -p ControlGroup --value sc117-tp-svc-pfh-locks-20261030)
  pids=$(cat "/sys/fs/cgroup$cg/cgroup.procs" 2>/dev/null | tr '\n' ' ')
  n=$(lslocks -n -o PID,PATH 2>/dev/null | awk -v p=" $pids " '$2 ~ /\/dev\/shm\/card(23|27|43|47)\.lock$/ && index(p, " "$1" ") {print $2}' | sort -u | wc -l)
  [ "$n" = 4 ] && { held=1; break; }
done
echo "lock holder: all four card locks held=$held at $(date -Is)"
[ "$held" = 1 ] || { echo "lock holder did not get all four locks"; systemctl --user stop sc117-tp-svc-pfh-locks-20261030; exit 1; }
for spec in "$@"; do
  IFS=: read -r name ctx rec <<<"$spec"
  [ "$(systemctl --user is-active sc117-tp-svc-pfh-locks-20261030)" = active ] || { echo "lock holder not active before $name"; break; }
  echo "--- server $name ctx $ctx ${rec:-} start $(date -Is)"
  systemd-run --user --unit=sc117-tp-svc-pfh-run-$name-c$ctx-20261030 -p Restart=no --wait --collect -E SC117_ENGINE_RECEIPT=$R -E ARM_CONTEXT=$ctx \
    -E ARM_RECORD_ORACLE=$([ "${rec:-}" = record ] && echo 1 || echo 0) bash $D/run_arm_suite.sh $name
  st=$(cat "$D/logs/STATUS-$name-c$ctx" 2>/dev/null); echo "server $name-c$ctx: $st at $(date -Is)"
  [ "$st" = "done $name-c$ctx" ] || { echo "HALT chain after $name-c$ctx"; break; }
done
systemctl --user stop sc117-tp-svc-pfh-locks-20261030
echo "=== chain end $(date -Is)"
