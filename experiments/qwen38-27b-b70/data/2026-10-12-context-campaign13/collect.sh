#!/usr/bin/env bash
# Evidence of campaigns 13 and 13b into the lab repo: small files only (logs, queues, runners, the sampler's table,
# per-run counters and grader output, the task's tickets and spec, the proxy's notes history and events; the whole
# conversation of each repair run as the client sent it; no context snapshots, no copy of the library).
# Run when no research server is up (the tables read job folders). Safe to run again: it only copies and rewrites.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-12-context-campaign13
O=/mnt/fast-ai/bench-results/context-longrun-20261012
O11=/mnt/fast-ai/bench-results/context-longrun-20261011
ODR=/mnt/fast-ai/bench-results/context-longrun-20261010/client-rules
ODH=$O11/client-hard; OD1M=$O11/client-1m
for f in campaign13.attempt1.log campaign13.log QUEUE13.txt longrun-campaign13.sh metrics-c13.attempt1.tsv metrics-c13.tsv \
         campaign13b.log QUEUE13B.txt longrun-campaign13b.sh metrics-c13b.tsv metrics-sampler.sh; do
  [[ -e $O/$f ]] && cp "$O/$f" "$D/"
done
for e in campaign13.err campaign13b.err; do [[ -s $O/$e ]] && cp "$O/$e" "$D/"; done
first() { ls -d "$1"/*/ 2>/dev/null | head -1; }

# ---- the repair task: what the agent was given and how it was graded (the library is rebuilt by make_repair_tasks.py)
for odx in "$O/client-repair" "$O/client-repair2"; do
  [[ -d $odx/tasks ]] || continue
  for t in "$odx"/tasks/repair-n*; do
    [[ -d $t ]] || continue
    out="$D/tasks/$(basename "$odx")/$(basename "$t")"; mkdir -p "$out"
    cp "$t/instruction.md" "$t/task.toml" "$t/tests/spec.json" "$t/tests/grade.py" "$t/environment/tickets.jsonl" \
       "$t/environment/Dockerfile" "$t/environment/next" "$t/environment/t" "$out/" 2>/dev/null
  done
  # ---- the repair runs (also the attempt the memory guard stopped)
  for j in "$odx"/runs/jobs/*__repair-*; do
    [[ -d $j ]] || continue
    t=$(first "$j"); [[ -n $t ]] || continue
    name=$(basename "$j"); out="$D/repair/$(basename "$odx")/$name"; mkdir -p "$out"
    for f in verifier/details.json verifier/test-stdout.txt agent/usage.json agent/timing.json agent/trajectory.json; do
      [[ -e $t/$f ]] && cp "$t/$f" "$out/$(basename "$f")"
    done
    arm=${name%%__*}; rest=${name#*__}                # XR__repair-n40-s0.guard-stop-1135 -> XR, repair-n40-s0.guard-stop-1135
    for x in settings.txt summary.txt; do cp "$odx/runs/$name.$x" "$out/" 2>/dev/null; done
    cp "$odx/runs/proxy-status-$name.json" "$out/proxy-status.json" 2>/dev/null
    for tag in c13 c13b; do
      s=$(first "$O/proxy-state/$tag-$arm-$rest")
      [[ -n $s ]] && { mkdir -p "$out/proxy"; cp "$s/notes-history.jsonl" "$s/events.jsonl" "$s/state.json" "$out/proxy/" 2>/dev/null; }
    done
  done
done

# ---- the ledger runs of part B (and of 13b)
cd "$CTX" || exit 2
python3 c10_table.py "$ODR" X32p X32q N32u --json "$D/table-rules-240k.json" > "$D/table-rules-240k.txt" 2>&1
python3 c10_table.py "$ODH" N32sr:0 N32z:0 N32nr:1 N32n:1 N32pr:1 N32p:1 --json "$D/table-hard-240k.json" > "$D/table-hard-240k.txt" 2>&1
python3 c10_table.py "$OD1M" N32u:0 X32p:0 N32n:1 N32p:1 X32q:1 --json "$D/table-1m.json" > "$D/table-1m.txt" 2>&1
for spec in "$ODH N32pr 1" "$ODH N32p 1" "$OD1M N32p 1"; do
  set -- $spec
  compgen -G "$1/runs/jobs/$2__sparse-memory-t*k-s$3/*/verifier/details.json" >/dev/null || continue
  python3 notes_audit.py "$1" "$2" "$3" > "$D/audit-$(basename "$1")-$2-s$3.txt" 2>&1
done
task_of() { python3 -c 'import json,sys,glob; g=glob.glob(sys.argv[1]+"/runs/jobs/"+sys.argv[2]+"__sparse-memory-t*k-s"+sys.argv[3]+"/*/config.json"); print(json.load(open(g[0]))["task"]["path"] if g else "")' "$1" "$2" "$3"; }
proxy() {  # label session_dir out_dir arm seed
  [[ -n $2 && -d $2 ]] || return 0
  local t; t=$(task_of "$3" "$4" "$5"); [[ -n $t ]] || return 0
  mkdir -p "$D/proxy/$1"
  python3 proxy_notes_audit.py "$2" "$t" > "$D/proxy/$1/notes-audit.txt" 2>&1
  cp "$2/notes-history.jsonl" "$2/events.jsonl" "$2/state.json" "$D/proxy/$1/" 2>/dev/null
}
proxy X32q-rules-s0 "$(first "$O/proxy-state/c13-X32q-240k-s0")" "$ODR" X32q 0
proxy X32q-rules-s1 "$(first "$O/proxy-state/c13-X32q-240k-s1")" "$ODR" X32q 1
proxy X32q-1m-s1 "$(first "$O/proxy-state/c13b-X32q-1000k-s1")" "$OD1M" X32q 1
for od in "$ODR" "$ODH" "$OD1M"; do
  for j in "$od"/runs/jobs/{X32q,N32p,N32pr}__*; do
    [[ -d $j ]] || continue
    t=$(first "$j"); [[ -n $t && -e $t/verifier/details.json ]] || continue
    out="$D/runs/$(basename "$od")/$(basename "$j")"; mkdir -p "$out"
    for f in agent/keeper_stats.json agent/keeper_calls.json agent/notes_final.txt agent/usage.json agent/timing.json verifier/details.json; do
      [[ -e $t/$f ]] && cp "$t/$f" "$out/$(basename "$f")"
    done
    cp "$od/runs/$(basename "$j").arm.txt" "$out/arm.txt" 2>/dev/null
    cp "$od"/proxy-status-c13*-"$(basename "$j" | cut -d_ -f1)"-*-s"$(basename "$j" | sed 's/.*-s//')".json "$out/" 2>/dev/null
  done
done
for tag in c13.attempt1 c13 c13b; do
  SRV=$O/server/tp2-w262144-$tag
  [[ -e $SRV/state.json ]] && cp "$SRV/state.json" "$D/server-state-$tag.json"
  [[ -e $SRV/MEMORY-GUARD.json ]] && cp "$SRV/MEMORY-GUARD.json" "$D/server-MEMORY-GUARD-$tag.json"
  [[ -e $SRV/memory-guard.jsonl ]] && python3 - "$SRV/memory-guard.jsonl" > "$D/server-host-memory-$tag.txt" <<'PY'
import json, sys
a = sorted(json.loads(l)["available"] / 2**30 for l in open(sys.argv[1]) if '"available"' in l)
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  1% {a[len(a)//100]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
done
# the last 30 seconds before the guard stopped the first start: the fall of 70 MiB a second
SRV=$O/server/tp2-w262144-c13.attempt1
[[ -e $SRV/memory-guard.jsonl ]] && tail -60 "$SRV/memory-guard.jsonl" > "$D/server-memory-guard-c13.attempt1-last-30s.jsonl"
du -sh "$D"; find "$D" -type f | wc -l
