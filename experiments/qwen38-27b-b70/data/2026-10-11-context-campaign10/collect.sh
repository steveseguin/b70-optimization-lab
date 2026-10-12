#!/usr/bin/env bash
# Evidence of campaign 10 into the lab repo: small files only (logs, tables, per-run counters, final NOTES, audits).
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-11-context-campaign10
O=/mnt/fast-ai/bench-results/context-longrun-20261011
ODR=/mnt/fast-ai/bench-results/context-longrun-20261010/client-rules
mkdir -p "$D"
cp "$O/campaign10.log" "$O/QUEUE10.txt" "$O/longrun-campaign10.sh" "$D/" 2>/dev/null
[[ -s $O/campaign10.err ]] && cp "$O/campaign10.err" "$D/campaign10.err"
cd "$CTX" || exit 2
python3 c10_table.py "$ODR" N32j N32j35 N32d N32e N32e35 N32e25 N32c35 N32x N32xth N32y N32z N32w N32v N32u R32 R32a R32b --json "$D/table-rules-240k.json" > "$D/table-rules-240k.txt" 2>&1
python3 c10_table.py "$O/client-1m" N32j:0 N32u:0 R32c40:0 --json "$D/table-1m.json" > "$D/table-1m.txt" 2>&1
python3 c10_table.py "$O/client-hard" N32z:0 --json "$D/table-hard-240k.json" > "$D/table-hard-240k.txt" 2>&1
for spec in "$ODR N32j 0" "$ODR N32j 1" "$ODR N32j35 0" "$ODR N32d 0" "$ODR N32e 0" "$ODR N32e35 0" "$ODR N32e25 0" "$ODR N32c35 0" "$ODR N32x 0" "$ODR N32xth 0" \
            "$ODR N32y 1" "$ODR N32z 0" "$ODR N32w 0" "$ODR N32v 1" "$ODR N32u 0" "$ODR N32u 1" "$O/client-1m N32j 0" "$O/client-1m N32u 0" "$O/client-hard N32z 0"; do
  set -- $spec
  compgen -G "$1/runs/jobs/$2__sparse-memory-t*k-s$3/*/verifier/details.json" >/dev/null || continue
  python3 notes_audit.py "$1" "$2" "$3" > "$D/audit-$(basename "$1")-$2-s$3.txt" 2>&1
done
for od in "$ODR" "$O/client-1m" "$O/client-hard"; do
  for j in "$od"/runs/jobs/{N32j35,N32d,N32e,N32e35,N32e25,N32c35,N32x,N32xth,N32y,N32z,N32w,N32v,N32u,R32,R32a,R32b,R32c40}__*; do
    [[ -d $j ]] || continue
    t=$(ls -d "$j"/*/ 2>/dev/null | head -1); [[ -n $t && -e $t/verifier/details.json ]] || continue
    out="$D/runs/$(basename "$od")/$(basename "$j")"; mkdir -p "$out"
    for f in agent/keeper_stats.json agent/keeper_calls.json agent/notes_final.txt agent/usage.json agent/timing.json verifier/details.json; do
      [[ -e $t/$f ]] && cp "$t/$f" "$out/$(basename "$f")"
    done
    cp "$od/runs/$(basename "$j").arm.txt" "$out/arm.txt" 2>/dev/null
  done
done
RT=/mnt/fast-ai/bench-results/context-longrun-20261010/client-rules/tasks/sparse-memory
{ for t in "$RT/sparse-memory-t240k-s0" "$RT/sparse-memory-t240k-s1" "$O/client-hard/tasks/sparse-memory/sparse-memory-t240k-s0" "$O/client-1m/tasks/sparse-memory/sparse-memory-t1000k-s0"; do
    echo "== $t"; python3 rag_coverage.py "$t" --k 20 40 80; done
  echo "== 1M with the earlier questions stored too"; python3 rag_coverage.py "$O/client-1m/tasks/sparse-memory/sparse-memory-t1000k-s0" --k 20 80 --with-questions; } > "$D/rag-coverage.txt" 2>&1
cp "$O/client-hard/snap/c10-R32b-240k-s0-answers-at-stop.json" "$D/hard-R32b-answers-at-stop.json" 2>/dev/null
cp "$O/client-hard/tasks/sparse-memory/sparse-memory-t240k-s0/tests/reference.json" "$D/hard-240k-s0-task-reference.json" 2>/dev/null
SRV=$O/server/tp2-w262144-c10
[[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD.json"
[[ -e $SRV/memory-guard.jsonl ]] && python3 - "$SRV/memory-guard.jsonl" > "$D/server-host-memory.txt" <<'PY'
import json, sys
a = sorted(json.loads(l)["available"] / 2**30 for l in open(sys.argv[1]) if '"available"' in l)
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  1% {a[len(a)//100]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
du -sh "$D"; find "$D" -type f | wc -l
