#!/usr/bin/env bash
# One server of research/aot-tp-2026-10-31/suite: the AOT A/B (A = JIT r1 40388fc92c43, B = the AOT build of the same tree
# and flags). Copy of research/two-card-flags-2026-10-31/suite/run_arm_suite.sh (itself from hc-split-2026-10-30's; steps,
# floors, gates and halts unchanged). Changes: paths, unit names (sc117-tp-svc-aot-*), port 18181, lock holder
# sc117-tp-svc-aot-locks-20261031; the layout (four cards: all four locks; two cards: card23 + card47) and the --wait-seconds
# deadline come from the arm (arm_env.py: SC117_LAB_WAIT_SECONDS=300 for the A/B arms, none for hspA60); the arm admits
# only its binary kind (arm_env.py ARM --binary: jit = the r1 receipt, aot = a receipt with aot_target); both ranks'
# environments are recorded from /proc after ready (logs/rank-env-ARM.txt); after the stop, startup_metrics.py writes
# the startup timeline (launch -> ready, first request, each rank's first half, the startup gate, the JIT caches).
# At 131072 the 121,854-token / 512-output long request follows the TTFT probe (long_probe.py, as hc-split's suite).
# Any failure halts (one cooperative stop of the service, no kill, no retry).
set -u
CTX=${ARM_CONTEXT:-65536}; export ARM_CONTEXT=$CTX
ENVARM=${1%-r[0-9]*}; ARM=$1-c$CTX; arm=$(echo "$ARM" | tr A-Z a-z)
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/aot-tp-2026-10-31/suite
LAN=/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/serving/lan
SUITE=/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/service-speed/d-mtp-fp8/suite/run_suite.py
W=/dev/shm/tp-svc-aot-20261031/arm-$arm
UNIT=sc117-tp-svc-aot-arm-$arm-20261031
PORT=18181
HOLDER=sc117-tp-svc-aot-locks-20261031
JIT_SHA=40388fc92c4322dba2976286d40c8eae78ec5e3fac75f82fe40d5259c4a09cee
OUT=$D/results/suite/arm-$ARM
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
  # tp-evidence also keeps every request's per-half rows (timings.jsonl, tens of MB): those stay in the work directory
  # (archived to RAID); only the small tp-*.json statistics are copied here.
  [ -n "$run" ] && [ -d "$run/tp-evidence" ] && { mkdir -p "$OUT/tp-evidence"; cp "$run"/tp-evidence/*tp-*.json "$OUT/tp-evidence/" 2>/dev/null; }
  cp "$W"/gate-evidence/f32-selftest-*.json "$W"/gate-evidence/f32-state-[0-9a-f]*.json "$OUT/" 2>/dev/null
  python3 "$D/collect_arm.py" "$W" "$OUT" || echo "collect_arm.py rc=$?"
  journalctl --user -u "$UNIT" --no-pager -o short-iso >"$OUT/service-journal.txt" 2>&1
}
halt() { echo "HALT: $1"; echo "HALT $ARM: $1" >"$D/logs/STATUS-$ARM"; stop_service; collect; python3 "$D/klog_check.py" "arm$ARM-after-halt" "$TA" "$D/logs/kernel-log-arm$ARM-after-halt.txt"; exit 1; }
TA=$(date +%s)
# ---- preconditions
[ "$(systemctl --user is-active $HOLDER)" = active ] || halt "card-lock holder not active"
[ -n "${SC117_ENGINE_RECEIPT:-}" ] && [ -f "$SC117_ENGINE_RECEIPT" ] || halt "SC117_ENGINE_RECEIPT not set"
BIN=$(basename "$SC117_ENGINE_RECEIPT" .json)
KIND=$(python3 -B "$D/arm_env.py" "$ENVARM" --binary) || halt "unknown arm $ENVARM"
python3 -B - "$SC117_ENGINE_RECEIPT" "$KIND" "$JIT_SHA" <<'PY' || halt "receipt does not match the arm's binary kind $KIND"
import json, sys
r = json.load(open(sys.argv[1])); kind, jit = sys.argv[2], sys.argv[3]
ok = r['binary_sha256'] == jit if kind == 'jit' else (r['binary_sha256'] != jit and r.get('aot_target') == 'intel_gpu_bmg_g31')
print('receipt', sys.argv[1], 'binary', r['binary_sha256'][:12], 'kind', kind, 'aot_target', r.get('aot_target')); sys.exit(0 if ok else 1)
PY
BDFS=$(python3 -B "$D/arm_env.py" "$ENVARM" | sed -n 's/^SC117_RANK_BDFS=//p')
case "$BDFS" in *+*) CARDS="23 27 43 47" ;; *) CARDS="23 47" ;; esac
for c in $CARDS; do flock -n "/dev/shm/card$c.lock" true && halt "/dev/shm/card$c.lock is not held"; done
echo "arm $ENVARM: binary kind $KIND, cards $CARDS, wait $(python3 -B "$D/arm_env.py" "$ENVARM" | sed -n 's/^SC117_LAB_WAIT_SECONDS=//p' | grep . || echo default-60)"
[ -e "$W" ] && halt "$W exists (fresh paths only)"
[ -e "$OUT" ] && halt "$OUT exists (fresh paths only)"
service_active && halt "$UNIT already active"
ss -ltn | grep -q ":$PORT " && halt "port $PORT in use"
avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo); echo "MemAvailable $avail"
[ "$avail" -ge 98806740766 ] || halt "MemAvailable $avail below the service start floor 98806740766"
root=$(df -B1 --output=avail / | tail -1); echo "root free $root"; [ "$root" -ge 27130000000 ] || halt "root free $root below the service start floor 27.13 GB"
python3 "$D/klog_check.py" "arm$ARM-before" $(( TA - 3600 )) "$D/logs/kernel-log-arm$ARM-before.txt" || halt "kernel log not clean before arm $ARM"
mkdir -p -m 700 "$W" "$W/control" "$W/evidence" "$W/gate-evidence"
for o in f32-state-oracle.json f32-state-oracle-ctx65536.json; do cp "$LAN/evidence/$o" "$W/gate-evidence/$o"; cmp "$LAN/evidence/$o" "$W/gate-evidence/$o" || halt "oracle copy $o"; done
RECORD=()
if [ "$CTX" = 131072 ]; then
  O131=$D/evidence/f32-state-oracle-ctx131072.json
  if [ -f "$O131" ]; then cp "$O131" "$W/gate-evidence/"; cmp "$O131" "$W/gate-evidence/f32-state-oracle-ctx131072.json" || halt "oracle copy ctx131072"; [ "${ARM_RECORD_ORACLE:-0}" = 1 ] && halt "ARM_RECORD_ORACLE=1 but $O131 exists"
  elif [ "${ARM_RECORD_ORACLE:-0}" = 1 ]; then RECORD=("--setenv=SC117_LAB_RECORD_ORACLE=f32-state-oracle-ctx131072.json"); echo "this server records f32-state-oracle-ctx131072.json"
  else halt "no $O131 and ARM_RECORD_ORACLE unset"; fi
fi
sha256sum "$W"/gate-evidence/*.json
# ---- service
ENVARGS=()
while IFS= read -r kv; do ENVARGS+=("--setenv=$kv"); done < <(python3 -B "$D/arm_env.py" "$ENVARM")
ENVARGS+=("${RECORD[@]}")
# aot-tp: the ranks' --wait-seconds deadline comes from the arm (SC117_LAB_WAIT_SECONDS=300 in arm_env.py for every A/B arm,
# none for hspA60, which keeps the 60 s default).
ENVARGS+=("--setenv=SC117_LAB_UNIT=$UNIT.service" "--setenv=SC117_LAB_CONTROL_PARENT=$W/control" "--setenv=SC117_LAB_EVIDENCE=$W/gate-evidence" "--setenv=SC117_EVIDENCE_PARENT=$W/evidence")
printf '%s\n' "${ENVARGS[@]}" >"$D/logs/arm-$ARM-unit-env.txt"
systemd-run --user --unit="$UNIT" --description="prefill-speed suite server $ARM (lab SC117 service, 127.0.0.1:$PORT)" \
  -p Restart=no -p KillMode=process -p KillSignal=SIGTERM -p SendSIGKILL=no -p TimeoutStopSec=infinity -p LimitAS=infinity \
  -p LimitCORE=0 -p LimitNOFILE=1048576 -p Nice=19 -p "CPUAffinity=0-3 16-19" -p "WorkingDirectory=$D/lab" "${ENVARGS[@]}" \
  /usr/bin/python3 -B -u "$D/lab/service.py" --bind 127.0.0.1 --port "$PORT" --lifetime-hours 3 || halt "systemd-run failed"
TS=$(date +%s); ready=0
for i in $(seq 1 540); do
  sleep 5
  code=$(curl -s -o "$W/health.json" -w '%{http_code}' "http://127.0.0.1:$PORT/health" 2>/dev/null)
  [ "$code" = 200 ] && { ready=1; break; }
  service_active || break
  (( i % 6 == 0 )) && echo "waiting $(( $(date +%s) - TS )) s: $(cat "$W/health.json" 2>/dev/null | head -c 300)"
done
echo "ready=$ready after $(( $(date +%s) - TS )) s: $(cat "$W/health.json" 2>/dev/null)"
[ "$ready" = 1 ] || halt "service not ready (state $(systemctl --user is-active "$UNIT"))"
python3 "$D/klog_check.py" "arm$ARM-after-ready" "$TA" "$D/logs/kernel-log-arm$ARM-after-ready.txt" || halt "kernel log after ready"
bash "$D/rank_env.sh" "$1" "$W" || echo "rank_env.sh rc=$?"
# prefill-speed-2026-10-29: no timing unless the service's one-time batched-prefill gate passed all 13 cases and batched
# reading is on (the service otherwise keeps serving token by token, as server tptsxqck-r1 did).
G=$(ls "$W"/control/run-*/prefill-gate.json 2>/dev/null | head -1)
python3 -c "import json,sys;g=json.load(open('$G'));h=json.load(open('$W/health.json'));c=g['cases'];print('startup prefill gate: passed',g['passed'],'cases',len(c),'passing',sum(x['passed'] for x in c),'health prefill_rows',h.get('prefill_rows'));sys.exit(0 if g['passed'] and len(c)==13 and all(x['passed'] for x in c) and h.get('prefill_rows')==256 else 1)" \
  || halt "startup batched-prefill gate not 13/13 (or batched reading off): $G"
# ---- suite (one cold request per frozen prompt, 512 cap, greedy)
mkdir -p "$OUT"
timeout 3600 python3 -B "$SUITE" --url "http://127.0.0.1:$PORT/v1/chat/completions" --label "tp-svc-aot-20261031-arm$ARM-$BIN-ctx$CTX-split23-prefill256" --out "$OUT/suite.json"
rc=$?; echo "suite rc=$rc at $(date -Is)"
if [ "$rc" -eq 0 ]; then
  timeout 900 python3 -B "$D/ttft_probe.py" --url "http://127.0.0.1:$PORT/v1/chat/completions" --out "$OUT/ttft-long.json"
  trc=$?; echo "ttft probe rc=$trc at $(date -Is)"; [ "$trc" -eq 0 ] || rc=$trc
fi
if [ "$rc" -eq 0 ] && [ "$CTX" = 131072 ]; then
  python3 "$D/klog_check.py" "arm$ARM-before-long" "$TA" "$D/logs/kernel-log-arm$ARM-before-long.txt" || halt "kernel log before the long request"
  avail=$(awk '/^MemAvailable:/{print $2*1024}' /proc/meminfo); echo "MemAvailable before the long request $avail"
  SC117_CONTEXT=$CTX SC117_RANK_BDFS=$(python3 -B "$D/arm_env.py" "$ENVARM" | sed -n 's/^SC117_RANK_BDFS=//p') \
    timeout 3700 python3 -B "$D/long_probe.py" --url "http://127.0.0.1:$PORT/v1/chat/completions" --out "$OUT/long512.json"
  lrc=$?; echo "long512 rc=$lrc at $(date -Is)"; [ "$lrc" -eq 0 ] || rc=$lrc
fi
service_active || halt "service exited during the suite"
python3 "$D/klog_check.py" "arm$ARM-after-suite" "$TA" "$D/logs/kernel-log-arm$ARM-after-suite.txt" || halt "kernel log after suite"
[ "$rc" -eq 0 ] || halt "suite rc=$rc"
# ---- graceful stop, drain, kernel log, collect
stop_service
service_active && halt "service did not stop"
collect
if [ ${#RECORD[@]} -gt 0 ]; then
  [ -f "$W/gate-evidence/f32-state-oracle-ctx131072.json" ] || halt "the recording server wrote no ctx131072 oracle"
  cp "$W/gate-evidence/f32-state-oracle-ctx131072.json" "$D/evidence/f32-state-oracle-ctx131072.json"; echo "recorded oracle copied to evidence/"
fi
[ -f "$OUT/terminal.json" ] || halt "no terminal.json (incident?)"
python3 -B "$D/startup_metrics.py" "$W" "$OUT" "$UNIT" || echo "startup_metrics.py rc=$?"
python3 "$D/klog_check.py" "arm$ARM-after" "$TA" "$D/logs/kernel-log-arm$ARM-after.txt" || halt "kernel log after arm $ARM"
echo "=== arm $ARM done $(date -Is)"
echo "done $ARM" >"$D/logs/STATUS-$ARM"
