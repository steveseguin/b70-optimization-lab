#!/usr/bin/env bash
# Device phase for the 2026-10-28 direct-store lab. Launched once, already holding both card locks:
#   systemd-run --user ... flock -n -E 75 /dev/shm/card23.lock flock -n -E 75 /dev/shm/card47.lock \
#     taskset -c 0-3,16-19 bash run_device_phase.sh
# Order: kernel-log check -> 4 KB one-round-trip smoke -> gate -> main (pre-scale gate inside, then full) -> owner_peer.
# Any xe kernel-log line, failed gate, or abnormal exit halts; nothing is retried. Do not edit while it runs.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/p2p/direct-store-2026-10-28
exec >>"$D/logs/driver.log" 2>&1
source "$D/env.sh"
echo "=== device phase start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //')"
echo started >"$D/logs/STATUS"
halt() { echo "HALT: $1"; echo "HALT: $1" >"$D/logs/STATUS"; exit 1; }
klog() { python3 "$D/klog_check.py" "$1" "$2" "$D/logs/kernel-log-$1.txt" || halt "kernel-log check '$1' failed (rc $?)"; }

# Before the first device run: the last 24 h must hold no xe/fault lines.
klog before-24h $(( $(date +%s) - 86400 ))
T0=$(date +%s); echo "T0=$T0"

echo "--- smoke: calibration + one 4 KB round trip"
"$D/bin/p2p_direct_store" --mode smoke --out "$D/results/smoke.json" --log-since "$T0" >"$D/logs/smoke.stdout" 2>&1
rc=$?; cat "$D/logs/smoke.stdout"; echo "smoke rc=$rc"
klog after-smoke "$T0"
[ "$rc" -eq 0 ] || halt "smoke rc=$rc"
python3 - "$D/results/smoke.json" <<'PY' || halt "smoke JSON gate failed"
import json, sys
j = json.load(open(sys.argv[1])); p = j["ping"][0]
ok = j["rc"] == 0 and p["ok"] == 1 and all(p[c]["mismatches"] == 0 and p[c]["timeout"] == 0 and p[c]["rounds_done"] == 1 for c in ("cardA", "cardB"))
print("smoke gate:", "PASS" if ok else "FAIL", json.dumps(p)); sys.exit(0 if ok else 1)
PY

echo "--- main: pre-scale gate, ping-pong, chain none/direct, chain none/memcpy"
"$D/bin/p2p_direct_store" --mode main --out "$D/results/main.json" --log-since "$T0" --tokens 10 --reps 7 --k1 200 --k2 2000 \
  >"$D/logs/main.stdout" 2>&1
rc=$?; cat "$D/logs/main.stdout"; echo "main rc=$rc"
klog after-main "$T0"
case "$rc" in 0|10) ;; *) halt "main rc=$rc" ;; esac

echo "--- owner_peer: engine copy-engine peer_copy, same session"
"$D/bin/owner_peer" >"$D/logs/owner_peer.stdout" 2>&1
rc=$?; cat "$D/logs/owner_peer.stdout"; echo "owner_peer rc=$rc"
klog after-owner-peer "$T0"
[ "$rc" -eq 0 ] || halt "owner_peer rc=$rc"
echo "=== device phase done $(date -Is)"
echo done >"$D/logs/STATUS"
