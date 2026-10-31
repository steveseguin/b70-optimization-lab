#!/usr/bin/env bash
# Host the four-card SC117 server on the LAN (owner request 2026-10-31): the lab TP service of
# research/tp/prefill-shexp-split-2026-10-31 (lab/service.py, lab/adapter6_tp.py, arm_env.py), committed engine build
# 37ee90a428cd, flag set tptsxqckhcbgls, 131,072-token context, 192.168.2.44:18160 (the old two-card sc117-lan address).
# Same launch as that folder's run_arm_suite.sh minus the timing suite: a lock holder unit keeps all four card locks;
# the service runs in its own transient unit (Restart=no, KillMode=process, no SIGKILL); one start, no retry.
# Stop: systemctl --user stop sc117-tp-svc-4card-lan.service   (graceful: FINISH both ranks, wait for drain)
#       then: systemctl --user stop sc117-tp-svc-4card-lan-locks.service
set -u
CTX=131072
NAME=4card-lan
R=/home/steve/llm-optimizations/experiments/own-xpu-runtime
D=$R/research/tp/prefill-shexp-split-2026-10-31
LAN=$R/gsq-rco-iq3s/serving/lan
HERE=$R/serving/four-card-lan
RECEIPT=$R/engine/receipts/37ee90a428cd.json
ARM=tptsxqckhcbgls
BIND=192.168.2.44
PORT=18160
LIFETIME_H=${LIFETIME_H:-47}
STAMP=$(date +%Y%m%d-%H%M%S)
W=/dev/shm/sc117-$NAME-$STAMP
UNIT=sc117-tp-svc-$NAME
LOCKS=sc117-tp-svc-$NAME-locks
mkdir -p "$HERE/logs"
exec > >(tee -a "$HERE/logs/serve-$STAMP.log") 2>&1
echo "=== $NAME start $(date -Is)"
die() { echo "STOP: $1"; exit 1; }
# ---- preconditions
[ -f "$RECEIPT" ] || die "no receipt $RECEIPT"
for u in "$UNIT" "$LOCKS" sc117-lan; do [ "$(systemctl --user is-active "$u" 2>/dev/null)" = active ] && die "$u is active"; done
ss -ltn | grep -q ":$PORT " && die "port $PORT in use"
avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo); echo "MemAvailable $avail"
[ "$avail" -ge 98806740766 ] || die "MemAvailable below the service start floor"
root=$(df -B1 --output=avail / | tail -1); echo "root free $root"; [ "$root" -ge 27130000000 ] || die "root free below 27.13 GB"
python3 "$D/klog_check.py" "$NAME-before" $(( $(date +%s) - 3600 )) "$HERE/logs/kernel-log-$STAMP-before.txt" || die "kernel log not clean"
# ---- card locks (held for the service's whole life)
systemd-run --user --unit="$LOCKS" -p Restart=no flock -w 600 -E 75 /dev/shm/card23.lock flock -w 600 -E 75 /dev/shm/card27.lock \
  flock -w 600 -E 75 /dev/shm/card43.lock flock -w 600 -E 75 /dev/shm/card47.lock sleep infinity || die "lock holder failed"
held=0
for i in $(seq 1 130); do
  [ "$(systemctl --user is-active "$LOCKS")" = active ] || break
  cg=$(systemctl --user show -p ControlGroup --value "$LOCKS")
  pids=" $(cat /sys/fs/cgroup$cg/cgroup.procs 2>/dev/null | tr '\n' ' ') "
  n=$(lslocks -n -o PID,PATH 2>/dev/null | awk -v p="$pids" '$2 ~ /\/dev\/shm\/card(23|27|43|47)\.lock$/ && index(p, " "$1" ") {print $2}' | sort -u | wc -l)
  [ "$n" = 4 ] && { held=1; break; }; sleep 5
done
[ "$held" = 1 ] || { systemctl --user stop "$LOCKS"; die "did not get all four card locks"; }
echo "all four card locks held by $LOCKS"
# ---- work dir and pinned oracles
mkdir -p -m 700 "$W" "$W/control" "$W/evidence" "$W/gate-evidence"
for o in f32-state-oracle.json f32-state-oracle-ctx65536.json; do cp "$LAN/evidence/$o" "$W/gate-evidence/$o"; done
cp "$R/research/tp/prefill-balance-2026-10-31/evidence/f32-state-oracle-ctx131072.json" "$W/gate-evidence/"
sha256sum "$W"/gate-evidence/*.json
# ---- service
ENVARGS=()
while IFS= read -r kv; do ENVARGS+=("--setenv=$kv"); done < <(SC117_ENGINE_RECEIPT=$RECEIPT ARM_CONTEXT=$CTX python3 "$D/arm_env.py" "$ARM")
ENVARGS+=("--setenv=SC117_LAB_WAIT_SECONDS=300" "--setenv=SC117_LAB_UNIT=$UNIT.service" "--setenv=SC117_LAB_CONTROL_PARENT=$W/control" \
  "--setenv=SC117_LAB_EVIDENCE=$W/gate-evidence" "--setenv=SC117_EVIDENCE_PARENT=$W/evidence")
printf '%s\n' "${ENVARGS[@]}" >"$HERE/logs/unit-env-$STAMP.txt"
systemd-run --user --unit="$UNIT" --description="SC117 four-card LAN server ($ARM, ctx $CTX, $BIND:$PORT)" \
  -p Restart=no -p KillMode=process -p KillSignal=SIGTERM -p SendSIGKILL=no -p TimeoutStopSec=infinity -p LimitAS=infinity \
  -p LimitCORE=0 -p LimitNOFILE=1048576 -p Nice=19 -p "CPUAffinity=0-3 16-19" -p "WorkingDirectory=$D/lab" "${ENVARGS[@]}" \
  /usr/bin/python3 -B -u "$D/lab/service.py" --bind "$BIND" --port "$PORT" --lifetime-hours "$LIFETIME_H" || die "systemd-run failed"
echo "service $UNIT started; work dir $W"
