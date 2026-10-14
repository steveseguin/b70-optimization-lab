#!/usr/bin/env bash
# Evidence of campaign 18 (2026-10-13/14): the log, queue and runner; the N2M and X2M runs on the 2M adversarial
# stream; the proxy's notes history and events; the server's state; the 2M comparison table with these rows.
# The generator, proxy code, runner and queue were committed before the runs. Safe to run again.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-13-context-campaign18
O=/mnt/fast-ai/bench-results/context-longrun-20261012
OD1M=/mnt/fast-ai/bench-results/context-longrun-20261011/client-1m
for f in campaign18.log QUEUE18.txt longrun-campaign18.sh; do
  [[ -e $O/$f ]] && cp "$O/$f" "$D/"
done
[[ -s $O/campaign18.err ]] && cp "$O/campaign18.err" "$D/"
first() { ls -d "$1"/*/ 2>/dev/null | head -1; }

for name in N2M__sparse-memory-t2000k-s0 X2M__sparse-memory-t2000k-s0; do
  j=$(ls -d "$OD1M/runs/jobs/$name"/*/ 2>/dev/null | head -1)
  [[ -n $j ]] || continue
  out="$D/stream/$name"; mkdir -p "$out"
  for f in verifier/details.json verifier/test-stdout.txt agent/usage.json agent/timing.json config.json; do
    [[ -e $j/$f ]] && cp "$j/$f" "$out/$(basename "$f")"
  done
  arm=${name%%__*}
  cp "$OD1M/arm-$arm-s0-c18.out" "$out/run.out" 2>/dev/null
  cp "$OD1M/proxy-status-c18-$arm-2000k-s0.json" "$out/proxy-status.json" 2>/dev/null
  s=$(python3 - "$O/proxy-state/c18-$arm-2000k-s0" <<'PY'
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

# the comparison table with the 2M rows added
python3 "$LAB/experiments/qwen38-27b-b70/scripts/context/c10_table.py" "$OD1M" N32u:0 X32p:0 W200:0 N2M:0 X2M:0 \
    --json "$D/table-2m.json" > "$D/table-2m.txt" 2>&1

SRV=$O/server/tp2-w262144-c18
[[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state-c18.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD-c18.json"
du -sh "$D"; find "$D" -type f | wc -l
