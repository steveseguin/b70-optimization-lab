#!/usr/bin/env bash
# Evidence of campaigns 11 and 12 into the lab repo: small files only (logs, queues, runners, tables, per-run
# counters, final NOTES, audits, the proxy's notes history and events; no trajectories, no snapshots).
# Run when no research server is up (the tables read job folders).
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-12-context-campaign11-12
O=/mnt/fast-ai/bench-results/context-longrun-20261012
O11=/mnt/fast-ai/bench-results/context-longrun-20261011
ODR=/mnt/fast-ai/bench-results/context-longrun-20261010/client-rules
ODC=$O11/client-crule; ODH=$O11/client-hard; OD1M=$O11/client-1m
for f in campaign11.log QUEUE11.txt longrun-campaign11.sh campaign12.log QUEUE12.txt longrun-campaign12.sh metrics-c12.tsv metrics-sampler.sh start-proxy-p.sh; do
  [[ -e $O/$f ]] && cp "$O/$f" "$D/"
done
for e in campaign11.err campaign12.err; do [[ -s $O/$e ]] && cp "$O/$e" "$D/"; done
cd "$CTX" || exit 2
python3 c10_table.py "$ODR" X32b X32i X32m X32n X32n2 X32p N32u --json "$D/table-rules-240k.json" > "$D/table-rules-240k.txt" 2>&1
python3 c10_table.py "$ODC" N32k:0 N32m:1 R32b --json "$D/table-crule-240k.json" > "$D/table-crule-240k.txt" 2>&1
python3 c10_table.py "$ODH" N32sr:0 N32z:0 N32nr:1 N32n:1 --json "$D/table-hard-240k.json" > "$D/table-hard-240k.txt" 2>&1
python3 c10_table.py "$OD1M" N32j:0 N32u:0 X32b:0 X32m:0 X32n2:0 X32p:0 N32n:1 --json "$D/table-1m.json" > "$D/table-1m.txt" 2>&1
# harness arms: NOTES audited against the true ledger
for spec in "$ODC N32k 0" "$ODC N32m 1" "$ODH N32nr 1" "$ODH N32n 1" "$OD1M N32n 1"; do
  set -- $spec
  compgen -G "$1/runs/jobs/$2__sparse-memory-t*k-s$3/*/verifier/details.json" >/dev/null || continue
  python3 notes_audit.py "$1" "$2" "$3" > "$D/audit-$(basename "$1")-$2-s$3.txt" 2>&1
done
# proxy arms: every saved NOTES version audited; notes history and events kept
task_of() { python3 -c 'import json,sys,glob; g=glob.glob(sys.argv[1]+"/runs/jobs/"+sys.argv[2]+"__sparse-memory-t*k-s"+sys.argv[3]+"/*/config.json"); print(json.load(open(g[0]))["task"]["path"] if g else "")' "$1" "$2" "$3"; }
proxy() {  # label session_dir out_dir arm seed
  [[ -d $2 ]] || return 0
  local t; t=$(task_of "$3" "$4" "$5"); [[ -n $t ]] || return 0
  mkdir -p "$D/proxy/$1"
  python3 proxy_notes_audit.py "$2" "$t" > "$D/proxy/$1/notes-audit.txt" 2>&1
  cp "$2/notes-history.jsonl" "$2/events.jsonl" "$2/state.json" "$D/proxy/$1/" 2>/dev/null
}
first() { ls -d "$1"/*/ 2>/dev/null | head -1; }
proxy X32i-rules-s0 "$(first "$O/proxy-state/c11-X32i-240k-s0")" "$ODR" X32i 0
proxy X32i-rules-s1 "$(first "$O/proxy-state/c11-X32i-240k-s1")" "$ODR" X32i 1
proxy X32m-rules-s0 "$O/proxy-state/m-shared/ce3c96361e3bf2dc" "$ODR" X32m 0
proxy X32m-rules-s1 "$O/proxy-state/m-shared/853755a555265b82" "$ODR" X32m 1
proxy X32m-1m-s0 "$O/proxy-state/m-shared/1a5e3739d935d6d3" "$OD1M" X32m 0
proxy X32n-rules-s0 "$(first "$O/proxy-state/c12-X32n-240k-s0")" "$ODR" X32n 0
proxy X32n-rules-s1 "$(first "$O/proxy-state/c12-X32n-240k-s1")" "$ODR" X32n 1
proxy X32n2-rules-s0 "$(first "$O/proxy-state/c12-X32n2-240k-s0")" "$ODR" X32n2 0
proxy X32n2-rules-s1 "$(first "$O/proxy-state/c12-X32n2-240k-s1")" "$ODR" X32n2 1
proxy X32n2-1m-s0 "$(first "$O/proxy-state/c12-X32n2-1000k-s0")" "$OD1M" X32n2 0
proxy X32p-rules-s0 "$O/proxy-state/p-shared/ce3c96361e3bf2dc" "$ODR" X32p 0
proxy X32p-rules-s1 "$O/proxy-state/p-shared/853755a555265b82" "$ODR" X32p 1
proxy X32p-1m-s0 "$O/proxy-state/p-shared/1a5e3739d935d6d3" "$OD1M" X32p 0
for od in "$ODR" "$ODC" "$ODH" "$OD1M"; do
  for j in "$od"/runs/jobs/{X32i,X32m,X32n,X32n2,X32p,N32k,N32m,N32n,N32nr,R32b}__*; do
    [[ -d $j ]] || continue
    [[ $(basename "$od") == client-rules && $(basename "$j") == R32b__* ]] && continue      # campaign 10's, already in its folder
    t=$(ls -d "$j"/*/ 2>/dev/null | head -1); [[ -n $t && -e $t/verifier/details.json ]] || continue
    out="$D/runs/$(basename "$od")/$(basename "$j")"; mkdir -p "$out"
    for f in agent/keeper_stats.json agent/keeper_calls.json agent/notes_final.txt agent/usage.json agent/timing.json verifier/details.json; do
      [[ -e $t/$f ]] && cp "$t/$f" "$out/$(basename "$f")"
    done
    cp "$od/runs/$(basename "$j").arm.txt" "$out/arm.txt" 2>/dev/null
    cp "$od"/proxy-status-c1[12]-"$(basename "$j" | cut -d_ -f1)"-*-s"$(basename "$j" | sed 's/.*-s//')".json "$out/" 2>/dev/null
  done
done
# the answers file of X32n seed 0 as it stood before the final overwrite (20 of 20 mid-stream answers right)
cp "$ODR"/snap/kept/c12-X32n-240k-s0-064835.json "$D/X32n-rules-s0-answers-before-the-final-write.json" 2>/dev/null
for tag in c11 c12; do
  SRV=$O/server/tp2-w262144-$tag
  [[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state-$tag.json"
  [[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD-$tag.json"
  [[ -e $SRV/memory-guard.jsonl ]] && python3 - "$SRV/memory-guard.jsonl" > "$D/server-host-memory-$tag.txt" <<'PY'
import json, sys
a = sorted(json.loads(l)["available"] / 2**30 for l in open(sys.argv[1]) if '"available"' in l)
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  1% {a[len(a)//100]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
done
du -sh "$D"; find "$D" -type f | wc -l
