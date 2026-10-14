#!/usr/bin/env bash
# Evidence of campaign 16 (2026-10-13): the log, queue and runner; the XR7 and C32 repair runs; the W200 1M
# stream run; the proxies' notes history and events; the diagnostic probe; the server's state.
# The proxy code, runner and queue were committed before the runs. Safe to run again.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-13-context-campaign16
O=/mnt/fast-ai/bench-results/context-longrun-20261012
ODX=$O/client-repair2
for f in campaign16.log QUEUE16.txt longrun-campaign16.sh; do
  [[ -e $O/$f ]] && cp "$O/$f" "$D/"
done
[[ -s $O/campaign16.err ]] && cp "$O/campaign16.err" "$D/"
first() { ls -d "$1"/*/ 2>/dev/null | head -1; }

for name in XR7__repair-n40-s2x XR7__repair-n40-s1x C32__repair-n40-s2x; do
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
  s=$(python3 - "$O/proxy-state/c16-$arm-$rest" <<'PY'
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

# W200 on the 1M rules stream, seed 0 (no proxy: the plain window at 204,800 tokens): verifier result, arm log, and
# the 1M comparison table with this row added.
OD1M=$O/client-1m
j=$(ls -d "$OD1M"/runs/jobs/W200__sparse-memory-t*k-s0/*/ 2>/dev/null | head -1)
if [[ -n $j ]]; then
  out="$D/stream/W200__1m-s0"; mkdir -p "$out"
  for f in verifier/details.json verifier/test-stdout.txt agent/usage.json agent/timing.json config.json; do
    [[ -e $j/$f ]] && cp "$j/$f" "$out/$(basename "$f")"
  done
  cp "$OD1M/arm-W200-s0-c16.out" "$out/run.out" 2>/dev/null
  python3 "$LAB/experiments/qwen38-27b-b70/scripts/context/c10_table.py" "$OD1M" N32u:0 X32p:0 W200:0 --json "$D/table-1m.json" > "$D/table-1m.txt" 2>&1
fi

SRV=$O/server/tp2-w262144-c16
[[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state-c16.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD-c16.json"
du -sh "$D"; find "$D" -type f | wc -l
