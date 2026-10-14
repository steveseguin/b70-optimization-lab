#!/usr/bin/env bash
# Evidence of campaign 17 (2026-10-13): the log, queue and runner; the XR8/X24/X16 repair runs on
# repair-n40-s2x; the proxies' notes history and events; the server's state.
# The proxy code, runner and queue were committed before the runs. Safe to run again.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-13-context-campaign17
O=/mnt/fast-ai/bench-results/context-longrun-20261012
ODX=$O/client-repair2
for f in campaign17.log QUEUE17.txt longrun-campaign17.sh; do
  [[ -e $O/$f ]] && cp "$O/$f" "$D/"
done
[[ -s $O/campaign17.err ]] && cp "$O/campaign17.err" "$D/"
first() { ls -d "$1"/*/ 2>/dev/null | head -1; }

for name in XR4__repair-n40-s2x XR8__repair-n40-s2x X24__repair-n40-s2x X16__repair-n40-s2x; do
  j="$ODX/runs/jobs/$name"
  [[ -d $j ]] || continue
  t=$(first "$j"); [[ -n $t ]] || continue
  out="$D/repair/$name"; mkdir -p "$out"
  for f in verifier/details.json verifier/test-stdout.txt agent/usage.json agent/timing.json agent/trajectory.json; do
    [[ -e $t/$f ]] && cp "$t/$f" "$out/$(basename "$f")"
  done
  cp "$ODX/runs/$name.out" "$out/run.out" 2>/dev/null
  cp "$ODX/runs/proxy-status-$name.json" "$out/proxy-status.json" 2>/dev/null
  arm=${name%%__*}; rest=${name#*__}
  s=$(python3 - "$O/proxy-state/c17-$arm-$rest" <<'PY'
import glob, json, os, sys
best, bestn = None, -1
for d in glob.glob(os.path.join(sys.argv[1], "*/")):
    try:
        n = json.load(open(os.path.join(d, "state.json"))).get("requests", 0)
    except Exception:
        continue
    if n > bestn:
        best, bestn = d, n
print(best or "")
PY
)
  [[ -n $s ]] && { mkdir -p "$out/proxy"; cp "$s/notes-history.jsonl" "$s/events.jsonl" "$s/state.json" "$out/proxy/" 2>/dev/null; }
done

SRV=$O/server/tp2-w262144-c17
[[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state-c17.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD-c17.json"
du -sh "$D"; find "$D" -type f | wc -l
