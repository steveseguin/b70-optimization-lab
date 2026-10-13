#!/usr/bin/env bash
# Evidence of campaign 14 (2026-10-13) into the lab repo: the log, queue and runner, per-run counters and grader
# output for the three repair arms (W32f on s1x; XR6 and W32g on the trap-free s2x), the proxy's notes history and
# events for XR6, and the server's state. The task itself (tasks/repair-n40-s2x) was committed at registration.
# Run when no research server is up. Safe to run again: it only copies.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-13-context-campaign14
O=/mnt/fast-ai/bench-results/context-longrun-20261012
ODX=$O/client-repair2
for f in campaign14.log QUEUE14.txt longrun-campaign14.sh; do
  [[ -e $O/$f ]] && cp "$O/$f" "$D/"
done
[[ -s $O/campaign14.err ]] && cp "$O/campaign14.err" "$D/"
first() { ls -d "$1"/*/ 2>/dev/null | head -1; }

for name in W32f__repair-n40-s1x XR6__repair-n40-s2x W32g__repair-n40-s2x; do
  j="$ODX/runs/jobs/$name"
  [[ -d $j ]] || continue
  t=$(first "$j"); [[ -n $t ]] || continue
  out="$D/repair/$name"; mkdir -p "$out"
  for f in verifier/details.json verifier/test-stdout.txt agent/usage.json agent/timing.json agent/trajectory.json; do
    [[ -e $t/$f ]] && cp "$t/$f" "$out/$(basename "$f")"
  done
  for x in settings.txt summary.txt; do cp "$ODX/runs/$name.$x" "$out/" 2>/dev/null; done
  cp "$ODX/runs/proxy-status-$name.json" "$out/proxy-status.json" 2>/dev/null
  arm=${name%%__*}; rest=${name#*__}
  s=$(first "$O/proxy-state/c14-$arm-$rest")
  [[ -n $s ]] && { mkdir -p "$out/proxy"; cp "$s/notes-history.jsonl" "$s/events.jsonl" "$s/state.json" "$out/proxy/" 2>/dev/null; }
done

# ---- the server session
SRV=$O/server/tp2-w262144-c14
[[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state-c14.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD-c14.json"
[[ -e $SRV/memory-guard.jsonl ]] && python3 - "$SRV/memory-guard.jsonl" > "$D/server-host-memory-c14.txt" <<'PY'
import json, sys
a = sorted(json.loads(l)["available"] / 2**30 for l in open(sys.argv[1]) if '"available"' in l)
if a: print(f"host memory available while the server ran: min {a[0]:.2f} 1% {a[len(a)//100]:.2f} median {a[len(a)//2]:.2f} GiB ({len(a)} samples)")
PY
du -sh "$D"; find "$D" -type f | wc -l
