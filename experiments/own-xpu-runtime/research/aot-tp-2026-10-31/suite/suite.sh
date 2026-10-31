#!/usr/bin/env bash
# The lab-service chain of research/aot-tp-2026-10-31/suite (copy of research/two-card-flags-2026-10-31/suite/suite.sh, from
# hc-split-2026-10-30's): fresh lab-service launches, in the given order, each once (run_arm_suite.sh), while
# sc117-tp-svc-aot-locks-20261031 holds the card locks of LOCKS (card numbers: "23 27 43 47" for the four-card chain,
# "23 47" for the two-card chain; bounded wait per lock, HOLD_WAIT s, default 1 h; the holder is --collect so a later chain can
# reuse its name). A failed or halted server ends the chain (nothing is
# retried). Then the lock holder stops. Usage: LOCKS="..." suite.sh RECEIPT.json NAME:CTX[:record[:RECEIPT]] ...
# (NAME = <arm>-r<N> of arm_env.py: hspJ-r1, hspA-r1, twoBJ-r1, ...; per-server RECEIPT as hc-split's.)
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/aot-tp-2026-10-31/suite
H=sc117-tp-svc-aot-locks-20261031
LOCKS=${LOCKS:?set LOCKS}; NL=$(echo $LOCKS | wc -w); PAT=$(echo $LOCKS | tr " " "|")
HOLD=(); for c in $LOCKS; do HOLD+=(flock -w "${HOLD_WAIT:-3600}" -E 75 /dev/shm/card$c.lock); done  # aot-tp: bounded wait per lock (HOLD_WAIT s)
R=$1; shift; [ -f "$R" ] || { echo "no receipt $R"; exit 1; }
exec >>"$D/logs/suite.log" 2>&1
echo "=== chain start $(date -Is): $*"
# prefill-host-2026-10-30: the holder waits (bounded, 1 h per lock) for a card another agent holds, and the chain starts
# only once every lock is held by a process of the holder unit's own cgroup.
systemd-run --user --unit=$H --collect -p Restart=no "${HOLD[@]}" sleep 28800 || { echo "lock holder failed"; exit 1; }
held=0
for i in $(seq 1 1500); do
  sleep 5
  [ "$(systemctl --user is-active $H)" = active ] || break
  cg=$(systemctl --user show -p ControlGroup --value $H)
  pids=$(cat "/sys/fs/cgroup$cg/cgroup.procs" 2>/dev/null | tr '\n' ' ')
  n=$(lslocks -n -o PID,PATH 2>/dev/null | awk -v p=" $pids " -v re="/dev/shm/card($PAT)[.]lock$" '$2 ~ re && index(p, " "$1" ") {print $2}' | sort -u | wc -l)
  [ "$n" = "$NL" ] && { held=1; break; }
done
echo "lock holder: card locks $LOCKS held=$held at $(date -Is)"
[ "$held" = 1 ] || { echo "lock holder did not get the locks $LOCKS"; systemctl --user stop $H; exit 1; }
for spec in "$@"; do
  IFS=: read -r name ctx rec rcpt <<<"$spec"; RR=${rcpt:-$R}; [ -f "$RR" ] || { echo "no receipt $RR for $name"; break; }  # hc-split: per-server receipt (A = m2, B = this folder's build)
  [ "$(systemctl --user is-active $H)" = active ] || { echo "lock holder not active before $name"; break; }
  # (as prefill-draft-batch-2026-10-30) wait, bounded, for MemAvailable to reach the service start floor before each server;
  # the server's own floor check still decides.
  for i in $(seq 1 360); do [ "$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo)" -ge 99806740766 ] && break; sleep 5; done
  echo "--- server $name ctx $ctx ${rec:-} receipt ${rcpt:-$R} start $(date -Is) MemAvailable $(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo)"
  systemd-run --user --unit=sc117-tp-svc-aot-run-$name-c$ctx-20261031 -p Restart=no --wait --collect -E SC117_ENGINE_RECEIPT=$RR -E ARM_CONTEXT=$ctx \
    -E ARM_RECORD_ORACLE=$([ "${rec:-}" = record ] && echo 1 || echo 0) bash $D/run_arm_suite.sh $name
  st=$(cat "$D/logs/STATUS-$name-c$ctx" 2>/dev/null); echo "server $name-c$ctx: $st at $(date -Is)"
  [ "$st" = "done $name-c$ctx" ] || { echo "HALT chain after $name-c$ctx"; break; }
done
systemctl --user stop $H
echo "=== chain end $(date -Is)"
