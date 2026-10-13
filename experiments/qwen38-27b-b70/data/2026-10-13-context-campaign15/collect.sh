#!/usr/bin/env bash
# Evidence of campaign 15 (2026-10-13): the log, queue and runner; both freeagent runs on repair-n40-s2x (FAp
# through the proxy, FAd direct); the proxy's notes history and events for FAp; the server's state.
# The agent program (tools/freeagent/) and the task were committed before the runs. Safe to run again.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-13-context-campaign15
O=/mnt/fast-ai/bench-results/context-longrun-20261012
ODX=$O/client-repair2
for f in campaign15.log QUEUE15.txt longrun-campaign15.sh; do
  [[ -e $O/$f ]] && cp "$O/$f" "$D/"
done
[[ -s $O/campaign15.err ]] && cp "$O/campaign15.err" "$D/"
first() { ls -d "$1"/*/ 2>/dev/null | head -1; }

for name in FAp__repair-n40-s2x FAd__repair-n40-s2x; do
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
  s=$(python3 - "$O/proxy-state/c15-$arm-$rest" <<'PY'
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

SRV=$O/server/tp2-w262144-c15
[[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state-c15.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD-c15.json"
du -sh "$D"; find "$D" -type f | wc -l
