#!/usr/bin/env bash
# Direct-store smoke on each NEW card pair before its first engine run (2026-10-29). Launched once as a transient user
# unit while sc117-tp-e2e-locks-20261029 holds all four card locks:
#   systemd-run --user --unit=sc117-tp-e2e-p2p-20261029 -p Restart=no taskset -c 0-3,16-19 bash run_pairs.sh
# Per pair: kernel-log check -> 4 KB one-round-trip smoke -> 10 KB chain (1-token pre-scale, then 3 x 10-token
# none/direct pairs) -> kernel-log check. Any xe line, mismatch, timeout or nonzero exit halts; nothing is retried.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/e2e-suite-2026-10-29
P=$D/p2p
exec >>"$D/logs/p2p.log" 2>&1
export PATH='/usr/bin:/bin' OMP_NUM_THREADS='2' HOME='/home/steve' ZE_ENABLE_PCI_ID_DEVICE_ORDER='1' ONEAPI_DEVICE_SELECTOR='level_zero:*'
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
echo "=== p2p pairs start $(date -Is) pid $$ affinity $(taskset -pc $$ | sed 's/.*: //')"
echo started >"$D/logs/P2P_STATUS"
halt() { echo "HALT: $1"; echo "HALT: $1" >"$D/logs/P2P_STATUS"; exit 1; }
klog() { python3 "$D/klog_check.py" "$1" "$2" "$D/logs/kernel-log-p2p-$1.txt" || halt "kernel-log check '$1' failed (rc $?)"; }
for pair in "23-27:0,1:0000:23:00.0:0000:27:00.0" "43-47:2,3:0000:43:00.0:0000:47:00.0"; do
  IFS=: read -r name mask a1 a2 a3 b1 b2 b3 <<<"$pair"
  A="$a1:$a2:$a3"; B="$b1:$b2:$b3"
  T0=$(date +%s)
  klog "$name-before" $(( T0 - 3600 ))
  echo "--- pair $name: A=$A B=$B ZE_AFFINITY_MASK=$mask"
  ZE_AFFINITY_MASK=$mask P2P_BDF_A=$A P2P_BDF_B=$B "$P/bin/p2p_direct_store_pair" --mode smoke --out "$D/results/p2p-$name-smoke.json" --log-since "$T0"
  rc=$?; echo "smoke $name rc=$rc"
  klog "$name-after-smoke" "$T0"
  [ "$rc" -eq 0 ] || halt "smoke $name rc=$rc"
  python3 - "$D/results/p2p-$name-smoke.json" <<'PY' || halt "smoke JSON gate $name"
import json, sys
j = json.load(open(sys.argv[1])); p = j["ping"][0]
ok = j["rc"] == 0 and p["ok"] == 1 and all(p[c]["mismatches"] == 0 and p[c]["timeout"] == 0 and p[c]["rounds_done"] == 1 for c in ("cardA", "cardB"))
print("smoke gate:", "PASS" if ok else "FAIL", json.dumps(j["devices"])); sys.exit(0 if ok else 1)
PY
  ZE_AFFINITY_MASK=$mask P2P_BDF_A=$A P2P_BDF_B=$B "$P/bin/p2p_direct_store_pair" --mode chain10 --out "$D/results/p2p-$name-chain10.json" --log-since "$T0" --tokens 10 --reps 3
  rc=$?; echo "chain10 $name rc=$rc"
  klog "$name-after-chain10" "$T0"
  [ "$rc" -eq 0 ] || halt "chain10 $name rc=$rc"
  python3 - "$D/results/p2p-$name-chain10.json" <<'PY' || halt "chain10 JSON gate $name"
import json, sys
j = json.load(open(sys.argv[1])); runs = j["chain10"]
bad = [r for r in runs if not r["ok"] or any(r[c][k] for c in ("cardA", "cardB") for k in ("own_mismatch", "peer_mismatch", "timeouts", "skipped", "abort", "budget_abort"))]
print("chain10 gate:", "PASS" if j["rc"] == 0 and not bad else "FAIL", len(runs), "runs", json.dumps(j.get("chain10_summary"))); sys.exit(0 if j["rc"] == 0 and not bad else 1)
PY
done
echo "=== p2p pairs done $(date -Is)"
echo done >"$D/logs/P2P_STATUS"
