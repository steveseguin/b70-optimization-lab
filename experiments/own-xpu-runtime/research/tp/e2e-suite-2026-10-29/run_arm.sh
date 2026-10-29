#!/usr/bin/env bash
# One arm of the 2026-10-29 four-card TP2xPP2 end-to-end suite. Launched once per arm (never retried) as its own
# transient runner unit while sc117-tp-e2e-locks-20261029 holds all four card locks:
#   systemd-run --user --unit=sc117-tp-e2e-run-<a|b|c>-20261029 -p Restart=no bash run_arm.sh <A|B|C>
# Steps: preconditions (lock holder, fresh paths, free port, MemAvailable >= the service start floor, kernel log clean)
# -> lab service in its own transient unit (Restart=no, KillMode=process, no SIGKILL, LimitNOFILE=1048576, nice 19,
# CPUs 0-3,16-19, 127.0.0.1:18171) -> wait for ready (load, F32 self-tests, F32 state oracle gate) -> run_suite.py
# once -> graceful unit stop (the service FINISHes both ranks and waits for drain) -> kernel log check -> collect.
# Any failure halts (one cooperative stop of the service, no kill, no retry).
set -u
ARM=$1; arm=$(echo "$ARM" | tr A-Z a-z)
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/e2e-suite-2026-10-29
LAN=/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/serving/lan
SUITE=/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/run_suite.py
W=/dev/shm/tp-e2e-20261029/arm-$arm
UNIT=sc117-tp-e2e-arm-$arm-20261029
PORT=18171
OUT=$D/results/arm-$ARM
exec >>"$D/logs/arm-$ARM.log" 2>&1
echo "=== arm $ARM start $(date -Is) pid $$"
echo "started $ARM" >"$D/logs/STATUS-$ARM"
service_active() { [ "$(systemctl --user is-active "$UNIT" 2>/dev/null)" = active ] || [ "$(systemctl --user is-active "$UNIT" 2>/dev/null)" = activating ] || [ "$(systemctl --user is-active "$UNIT" 2>/dev/null)" = deactivating ]; }
stop_service() {  # one cooperative stop; wait (bounded) for the service's own drain and exit
  if service_active; then
    echo "stopping $UNIT at $(date -Is)"; systemctl --user stop --no-block "$UNIT"
    for i in $(seq 1 360); do service_active || break; sleep 5; done
    service_active && echo "WARNING: $UNIT still active 30 min after the stop request (left alone: no kill)"
  fi
  echo "service state: $(systemctl --user is-active "$UNIT" 2>/dev/null) result: $(systemctl --user show "$UNIT" --property=Result,ExecMainStatus 2>/dev/null | tr '\n' ' ')"
}
collect() {
  mkdir -p "$OUT"
  run=$(ls -d "$W"/control/run-* 2>/dev/null | head -1)
  [ -n "$run" ] && for f in run.json plan.json monitor.json selftest-result.json requests.jsonl terminal.json incident.json prefill-gate.json rank0.log rank1.log rank0-launch.json rank1-launch.json; do
    [ -f "$run/$f" ] && cp "$run/$f" "$OUT/$f"; [ -f "$run/ranks/$f" ] && cp "$run/ranks/$f" "$OUT/$f"; done
  [ -n "$run" ] && [ -d "$run/tp-evidence" ] && cp -r "$run/tp-evidence" "$OUT/"
  cp "$W"/gate-evidence/f32-selftest-*.json "$W"/gate-evidence/f32-state-1*.json "$OUT/" 2>/dev/null
  python3 "$D/collect_arm.py" "$W" "$OUT" || echo "collect_arm.py rc=$?"
  journalctl --user -u "$UNIT" --no-pager -o short-iso >"$OUT/service-journal.txt" 2>&1
}
halt() { echo "HALT: $1"; echo "HALT $ARM: $1" >"$D/logs/STATUS-$ARM"; stop_service; collect; python3 "$D/klog_check.py" "arm$ARM-after-halt" "$TA" "$D/logs/kernel-log-arm$ARM-after-halt.txt"; exit 1; }
TA=$(date +%s)
# ---- preconditions
[ "$(systemctl --user is-active sc117-tp-e2e-locks-20261029)" = active ] || halt "card-lock holder not active"
for f in /dev/shm/card23.lock /dev/shm/card27.lock /dev/shm/card43.lock /dev/shm/card47.lock; do flock -n "$f" true && halt "$f is not held"; done
[ -e "$W" ] && halt "$W exists (fresh paths only)"
[ -e "$OUT" ] && halt "$OUT exists (fresh paths only)"
service_active && halt "$UNIT already active"
ss -ltn | grep -q ":$PORT " && halt "port $PORT in use"
avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo); echo "MemAvailable $avail"
[ "$avail" -ge 98806740766 ] || halt "MemAvailable $avail below the service start floor 98806740766"
python3 "$D/klog_check.py" "arm$ARM-before" $(( TA - 3600 )) "$D/logs/kernel-log-arm$ARM-before.txt" || halt "kernel log not clean before arm $ARM"
mkdir -p -m 700 "$W" "$W/control" "$W/evidence" "$W/gate-evidence"
for o in f32-state-oracle.json f32-state-oracle-ctx32768.json; do cp "$LAN/evidence/$o" "$W/gate-evidence/$o"; cmp "$LAN/evidence/$o" "$W/gate-evidence/$o" || halt "oracle copy $o"; done
sha256sum "$W"/gate-evidence/*.json
# ---- service
ENVARGS=()
while IFS= read -r kv; do ENVARGS+=("--setenv=$kv"); done < <(python3 "$D/arm_env.py" "$ARM")
ENVARGS+=("--setenv=SC117_LAB_UNIT=$UNIT.service" "--setenv=SC117_LAB_CONTROL_PARENT=$W/control" "--setenv=SC117_LAB_EVIDENCE=$W/gate-evidence" "--setenv=SC117_EVIDENCE_PARENT=$W/evidence")
printf '%s\n' "${ENVARGS[@]}" >"$D/logs/arm-$ARM-unit-env.txt"
systemd-run --user --unit="$UNIT" --description="TP2xPP2 e2e suite arm $ARM (lab SC117 service, 127.0.0.1:$PORT)" \
  -p Restart=no -p KillMode=process -p KillSignal=SIGTERM -p SendSIGKILL=no -p TimeoutStopSec=infinity -p LimitAS=infinity \
  -p LimitCORE=0 -p LimitNOFILE=1048576 -p Nice=19 -p "CPUAffinity=0-3 16-19" -p "WorkingDirectory=$D/lab" "${ENVARGS[@]}" \
  /usr/bin/python3 -B -u "$D/lab/service.py" --bind 127.0.0.1 --port "$PORT" --lifetime-hours 3 || halt "systemd-run failed"
TS=$(date +%s); ready=0
for i in $(seq 1 360); do
  sleep 5
  code=$(curl -s -o "$W/health.json" -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null)
  [ "$code" = 200 ] && { ready=1; break; }
  service_active || break
  (( i % 6 == 0 )) && echo "waiting $(( $(date +%s) - TS )) s: $(cat "$W/health.json" 2>/dev/null | head -c 300)"
done
echo "ready=$ready after $(( $(date +%s) - TS )) s: $(cat "$W/health.json" 2>/dev/null)"
[ "$ready" = 1 ] || halt "service not ready (state $(systemctl --user is-active "$UNIT"))"
python3 "$D/klog_check.py" "arm$ARM-after-ready" "$TA" "$D/logs/kernel-log-arm$ARM-after-ready.txt" || halt "kernel log after ready"
# ---- suite (one cold request per frozen prompt, 512 cap, greedy)
mkdir -p "$OUT"
timeout 3600 python3 -B "$SUITE" --url "http://127.0.0.1:$PORT/v1/chat/completions" --label "tp-e2e-20261029-arm$ARM-16ed1ff1a203-ctx32768-split23" --out "$OUT/suite.json"
rc=$?; echo "suite rc=$rc at $(date -Is)"
service_active || halt "service exited during the suite"
python3 "$D/klog_check.py" "arm$ARM-after-suite" "$TA" "$D/logs/kernel-log-arm$ARM-after-suite.txt" || halt "kernel log after suite"
[ "$rc" -eq 0 ] || halt "suite rc=$rc"
# ---- graceful stop, drain, kernel log, collect
stop_service
service_active && halt "service did not stop"
collect
[ -f "$OUT/terminal.json" ] || halt "no terminal.json (incident?)"
python3 "$D/klog_check.py" "arm$ARM-after" "$TA" "$D/logs/kernel-log-arm$ARM-after.txt" || halt "kernel log after arm $ARM"
echo "=== arm $ARM done $(date -Is)"
echo "done $ARM" >"$D/logs/STATUS-$ARM"
