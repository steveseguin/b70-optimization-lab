#!/usr/bin/env bash
# The research/tp/ctx131072-2026-10-29 lab-service chain: fresh lab-service launches, in the given order, each once
# (run_arm_suite.sh), while sc117-tp-svc-ctx-locks-20261029 holds all four card locks. A failed or halted server ends the
# chain (nothing is retried). Then the lock holder stops. Usage: suite.sh RECEIPT.json NAME:CTX[:record] ...
# (NAME = <arm>-r<N> of arm_env.py; CTX 65536 or 131072; record = ARM_RECORD_ORACLE=1 for the first 131072 server.)
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/ctx131072-2026-10-29
R=$1; shift; [ -f "$R" ] || { echo "no receipt $R"; exit 1; }
exec >>"$D/logs/suite.log" 2>&1
echo "=== chain start $(date -Is): $*"
systemd-run --user --unit=sc117-tp-svc-ctx-locks-20261029 -p Restart=no flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card27.lock \
  flock -n -E 75 /dev/shm/card43.lock flock -n -E 75 /dev/shm/card47.lock sleep 28800 || { echo "lock holder failed"; exit 1; }
sleep 2
for spec in "$@"; do
  IFS=: read -r name ctx rec <<<"$spec"
  [ "$(systemctl --user is-active sc117-tp-svc-ctx-locks-20261029)" = active ] || { echo "lock holder not active before $name"; break; }
  echo "--- server $name ctx $ctx ${rec:-} start $(date -Is)"
  systemd-run --user --unit=sc117-tp-svc-ctx-run-$name-c$ctx-20261029 -p Restart=no --wait --collect -E SC117_ENGINE_RECEIPT=$R -E ARM_CONTEXT=$ctx \
    -E ARM_RECORD_ORACLE=$([ "${rec:-}" = record ] && echo 1 || echo 0) bash $D/run_arm_suite.sh $name
  st=$(cat "$D/logs/STATUS-$name-c$ctx" 2>/dev/null); echo "server $name-c$ctx: $st at $(date -Is)"
  [ "$st" = "done $name-c$ctx" ] || { echo "HALT chain after $name-c$ctx"; break; }
done
systemctl --user stop sc117-tp-svc-ctx-locks-20261029
echo "=== chain end $(date -Is)"
