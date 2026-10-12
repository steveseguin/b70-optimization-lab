#!/usr/bin/env bash
# Campaign 13b (2026-10-12 afternoon): the repair marathon on a second seed, with an audit ticket at the end; then the
# two 1M ledger runs that campaign 13 gave up for it.
# Arms from a QUEUE file, one line per run: "ARM STREAM SEED [CAP_SECONDS]" with STREAM one of
#   rules (240K, seeds 0 1)   hard (240K, --pronouns --relative; seeds 0 1)   crule   1m (1M, seeds 0 1)
#   repair (make_repair_tasks.py: more-itertools 10.7.0 with 40 injected defects, tickets one at a time, three
#           standing rules that arrive as notices; the task is client-repair/tasks/repair-n40-s<SEED>)
# Arms on the ledger streams:  X32p  the proxy with today's afternoon code (a questioned notes reply is answered with
#               the lines in question only; an amount may be another thing's value); N32p / N32pr the harness keeper
#               with the same checks and no fall back to the full rewrite (see second-comparison.sh)
# Arms on repair, all with thinking on in every call:  XR  the plain agent through the proxy (32K window, in-place
#               notes, checks off, the rules recited when a ticket arrives)   W32  a 32K sliding window (oldest turns
#               dropped)   C32  summary compaction at 32K   A  the whole history in the 262K window
# Lines can be appended while the campaign runs; an empty queue for IDLE_MAX seconds, or the file STOP-CAMPAIGN13B,
# ends it. Server: the two-card recipe at --max-model-len 262144, guard floor 1.6 GiB (owner-approved research
# value), started once, never restarted; stopped only when no request is running. Gemma LAN service: stopped first,
# the same recipe reinstalled at the end unless a GPU fault line was logged.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
O=/mnt/fast-ai/bench-results/context-longrun-20261012
O11=/mnt/fast-ai/bench-results/context-longrun-20261011
SRV=$O/server/tp2-w262144-c13b
O10=/mnt/fast-ai/bench-results/context-longrun-20261010
OD1M=$O11/client-1m
ODC=$O11/client-crule
ODR=$O10/client-rules
ODH=$O11/client-hard
Q=${QUEUE:-$O/QUEUE13B.txt}
PORT=18196
PY=/mnt/fast-ai/venvs/clm/bin/python
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
GEMMA_RECIPE=${GEMMA_RECIPE:-throughput}
IDLE_MAX=${IDLE_MAX:-600}
ODX=$O/client-repair2
MAX_STEPS_REPAIR=${MAX_STEPS_REPAIR:-900}
RECITE_RE_REPAIR='(?m)^TICKET \d+/\d+ \((BUG|NOTICE)\)'
PPORT=18200
THINK_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)|^PROBE:|STREAM END|NOT RUN|Traceback|\(exit_code=[1-9-]'
RECITE_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)'
UNTIL_RE='(?m)^ITEM \d+/\d+ \(UPDATE\)'
SCAN_RE='(?m)^ITEM \d+/\d+ \(UPDATE\)'
LABEL_RE='(?m)^ITEM (\d+)/'
SP240="--density 3 --words --probes-every 25 --probes-k 3 --rules"
SPHARD="--density 3 --words --pronouns --relative --probes-every 25 --probes-k 3 --rules"
SP1M="--density 3 --words --probes-every 20 --probes-k 5 --rules"
SPCR="--density 3 --words --probes-every 25 --probes-k 3 --rules --class-rule"
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
avail() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }
faults() { journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
server_up() { curl -fsS -m 10 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; }
wait_idle() {  # no request running on the server for two polls in a row (at most 3 min)
  local r quiet=0
  for i in $(seq 1 60); do
    r=$(curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" 2>/dev/null | awk '/^vllm:num_requests_(running|waiting)/ {s+=$NF} END {print s+0}')
    if [[ $r == 0 ]]; then quiet=$((quiet+1)); (( quiet >= 2 )) && return 0; else quiet=0; fi
    sleep 3
  done
  return 1
}
mline() {  # server totals so far: prompt tokens, of which served from the prefix cache, and generated tokens
  curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" 2>/dev/null | awk '/^vllm:prefix_cache_queries_total/ {q=$NF} /^vllm:prefix_cache_hits_total/ {h=$NF} /^vllm:generation_tokens_total/ {g=$NF} END {printf "server totals: prompt %d cached %d generated %d", q, h, g}'
}
stream_of() {  # stream name -> "out_dir size" and the generator options in SP
  case "$1" in
    rules) SP=$SP240;  echo "$ODR 240000" ;;
    hard)  SP=$SPHARD; echo "$ODH 240000" ;;
    crule) SP=$SPCR;   echo "$ODC 240000" ;;
    1m)    SP=$SP1M;   echo "$OD1M 1000000" ;;
    *) return 1 ;;
  esac
}
task_dir() { ls -d "$1"/tasks/sparse-memory/sparse-memory-t*k-s"$3" 2>/dev/null | head -1; }   # out_dir size seed

say "campaign 13b start; queue $Q ($(grep -cvE '^\s*(#|$)' "$Q" 2>/dev/null || echo 0) lines); MemAvailable $(avail) MiB"
[[ -s $Q ]] || { say "ABORT: the queue file is missing or empty"; exit 2; }
[[ -e $SRV ]] && { say "ABORT: $SRV already exists"; exit 2; }
ss -tln | grep -q ":$PORT " && { say "ABORT: port $PORT is in use"; exit 2; }
ss -tln | grep -q ":$PPORT " && { say "ABORT: proxy port $PPORT is in use"; exit 2; }
[[ -n $(docker ps -q --filter name=fp8-tp) ]] && { say "ABORT: an fp8 container is already running"; exit 2; }
cd "$CTX" || exit 2

# ---- every queued line must name a known arm and an existing task (nothing is generated while the server is up)
while read -r arm stream seed cap; do
  [[ -z $arm || $arm == \#* ]] && continue
  if [[ $stream == repair ]]; then
    [[ $arm =~ ^(XR[a-z0-9]*|W32|C32|A)$ ]] || { say "ABORT: unknown repair arm '$arm'"; exit 2; }
    [[ -e $ODX/tasks/repair-n40-s$seed/tests/spec.json ]] || { say "ABORT: no task $ODX/tasks/repair-n40-s$seed"; exit 2; }
    continue
  fi
  set -- $(stream_of "$stream" || echo "") ; od=${1:-}; size=${2:-}
  [[ -n $od ]] || { say "ABORT: unknown stream '$stream' in the queue"; exit 2; }
  stream_of "$stream" >/dev/null     # sets SP in this shell
  [[ -n $(task_dir "$od" "$size" "$seed") ]] || { say "ABORT: no task for $stream seed $seed under $od"; exit 2; }
  env OUT_DIR="$od" API_BASE="http://127.0.0.1:$PORT/v1" CTXKEEPER_BASE="http://127.0.0.1:$PPORT/v1" MODEL_NAME=qwen38-27b-fp8 SPARSE_ARGS="$SP" MAX_TOKENS=8192 KINDS=sparse SEEDS="$seed" SIZES="$size" \
      SUBSET=core ARMS="$arm" DRY_RUN=1 ./second-comparison.sh > "$od/plan-campaign13b.out" 2>&1 || { say "ABORT: planning failed for $arm $stream $seed"; tail -3 "$od/plan-campaign13b.out"; exit 2; }
done < "$Q"
mkdir -p "$OD1M/snap/kept" "$ODR/snap/kept" "$ODH/snap/kept" "$ODC/snap/kept" "$O/proxy-state" "$ODX/runs"
say "queue checked: $(grep -vE '^\s*(#|$)' "$Q" | tr '\n' ';')"

# ---- Gemma off (wait for an idle front door, at most 10 min)
st="down down"
for i in $(seq 1 60); do
  st=$(curl -fsS -m 3 http://127.0.0.1:8000/v1/frontdoor/status 2>/dev/null | python3 -c 'import json,sys; f=json.load(sys.stdin)["frontdoor"]; print(f["active_generations"], f["queued_generations"])' 2>/dev/null || echo "down down")
  [[ $st == "0 0" || $st == "down down" ]] && break
  (( i % 6 == 1 )) && say "Gemma front door busy ($st active/queued); waiting"
  sleep 10
done
say "stopping the Gemma service (front door state: $st)"
sudo -A systemctl stop gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service
sudo -A systemctl reset-failed gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service 2>/dev/null
for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 2; done
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server still running"; exit 2; }
sleep 5
say "cards free; MemAvailable $(avail) MiB"

# ---- server (once)
systemctl --user reset-failed ctx-fp8-tp2-server 2>/dev/null
systemd-run --user --unit=ctx-fp8-tp2-server --collect -p WorkingDirectory=$LAB -E B70_GUARD_MIN_AVAILABLE_GIB=1.6 \
  python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py --out "$SRV" --port $PORT \
  --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800 \
  --tp 2 --mem 0.95 --max-model-len 262144 --batched 832 --fa-verify-rows --mtp 5 --draft-int4 \
  --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
  --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 \
  --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
  --serve-arg=--enable-auto-tool-choice --serve-arg=--tool-call-parser=qwen3_coder --serve-arg=--reasoning-parser=qwen3 \
  --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
  --serve-arg=--prefix-cache-retention-interval=13312 \
  --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
  --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 2>&1 | tail -1
ready=0
for i in $(seq 1 120); do
  if server_up; then ready=1; say "server ready after ~$((i*15)) s; MemAvailable $(avail) MiB"; break; fi
  systemctl --user is-active --quiet ctx-fp8-tp2-server || { say "server unit ended before ready"; break; }
  sleep 15
done

keep_best() {  # snap_dir tag: the new copy becomes the current one unless it lost probe answers the current one has
  python3 - "$1/$2-answers.tmp" "$1/$2-answers.json" <<'PY'
import json, os, re, sys
new, cur = sys.argv[1:3]
def probes(path):
    try:
        return {k for k in json.load(open(path)) if re.fullmatch(r"p\d+_\d+", k)}
    except Exception:
        return None
n, c = probes(new), probes(cur)
if n is not None and (c is None or c <= n):
    os.replace(new, cur)
else:
    os.replace(new, cur.replace("-answers.json", "-answers-after-loss.json"))
PY
}
snap_loop() {  # snap_dir tag: copy /app/answers.json out of the task container every 2 minutes while the arm runs
  local sd=$1 tag=$2 c
  while :; do
    sleep 120
    c=$(docker ps --filter name=sparse- --format '{{.Names}}' | head -1)
    [[ -n $c ]] && docker cp "$c:/app/answers.json" "$sd/$tag-answers.tmp" >/dev/null 2>&1 \
      && cp "$sd/$tag-answers.tmp" "$sd/kept/$tag-$(date +%H%M%S).json" \
      && keep_best "$sd" "$tag" && date +%s > "$sd/$tag-answers.at"
  done
}
result_line() {  # out_dir arm seed: score by type, calls, notes and retrieval counters of the finished trial
  python3 - "$1" "$2" "$3" <<'PY'
import glob, json, sys
od, arm, seed = sys.argv[1:4]
g = glob.glob(f"{od}/runs/jobs/{arm}__sparse-memory-t*k-s{seed}/*/")
if not g:
    print("   no trial directory"); sys.exit()
t = g[0]
def load(name):
    try:
        return json.load(open(t + name))
    except Exception:
        return None
d, u, s, k = load("verifier/details.json"), load("agent/usage.json"), load("agent/keeper_stats.json"), load("agent/keeper_calls.json")
if d:
    by = {}
    try:
        ref = json.load(open(json.load(open(t + "config.json"))["task"]["path"] + "/tests/reference.json"))["probes"]
        for key, res in d.get("per_key", {}).items():
            typ = ref[key]["type"] if key in ref else "final"
            a = by.setdefault(typ, [0, 0]); a[0] += res == "correct"; a[1] += 1
    except Exception as exc:
        by = {"(no breakdown)": [0, 0]}
    print(f"   RESULT {arm} seed {seed}: {d.get('correct')}/{d.get('n')} void={d.get('void')} violations={len(d.get('violations') or [])} "
          f"archive={d.get('archive')} counts={d.get('counts')}")
    print("   by type:", "  ".join(f"{a} {b[0]}/{b[1]}" for a, b in by.items()))
    try:
        spec = json.load(open(json.load(open(t + "config.json"))["task"]["path"] + "/tests/spec.json"))
        word = (spec.get("rules") or {}).get("class_word")
        if word:
            gov = [k for k, v in spec["expected"].items() if v == word]
            print(f"   rule by condition: {sum(d['per_key'].get(k) == 'correct' for k in gov)}/{len(gov)} of the questions whose answer is the word {word}; "
                  f"{sum(d['per_key'].get(k) == 'correct' for k in spec['expected'] if k not in gov)}/{len(spec['expected']) - len(gov)} of the others")
    except Exception as exc:
        print("   (no rule-by-condition breakdown:", exc, ")")
if u:
    print(f"   calls {u.get('n_lm_calls')} (main loop {u.get('total_iters')}), main-loop tokens written {u.get('completion_tokens')}, prompt {u.get('prompt_tokens')} cached {u.get('cached_tokens')}")
if s:
    print("   keeper:", {a: s.get(a) for a in ("notes_mode", "notes_calls", "notes_failed", "delta_fallbacks", "sums_corrected", "rules_put_back", "recitals", "retrievals", "retrieved_chars", "repeats_refused", "thinking_on_calls", "answers_put_back")}, "rules kept:", len(s.get("rules") or []))
if k:
    print(f"   notes calls: tokens written {sum(c.get('notes_completion_tokens', 0) for c in k)}, read {sum(c.get('notes_prompt_tokens', 0) for c in k)}, cuts {len(k)}, fallbacks {[c['delta_fallback'][:70] for c in k if c.get('delta_fallback')][:4]}")
PY
}
start_proxy() {  # state tag: one fresh proxy per X32i run
  systemctl --user reset-failed ctx-keeper-proxy 2>/dev/null
  systemd-run --user --unit=ctx-keeper-proxy --collect -p WorkingDirectory=$LAB python3 tools/ctxkeeper/ctxkeeper.py \
    --upstream "http://127.0.0.1:$PORT" --port $PPORT --budget 32768 --reply-reserve 2048 --headroom 1024 --target-ratio 0.6 \
    --notes-thinking on --effort medium --think-when "$THINK_RE" --think-until "$UNTIL_RE" --recite-when "$RECITE_RE" \
    --notes-mode inplace --inplace-tokens 15000 --notes-checks near --max-recalls 16 --notes-scan "$SCAN_RE" --recall-label "$LABEL_RE" --recall-unit item --state-dir "$O/proxy-state/$1" 2>&1 | tail -1
  for i in $(seq 1 30); do curl -fsS -m 3 "http://127.0.0.1:$PPORT/v1/models" >/dev/null 2>&1 && return 0; sleep 1; done
  say "proxy did not come up"; return 1
}
stop_proxy() {  # status file: keep the proxy's own counters, then stop it
  curl -fsS -m 5 "http://127.0.0.1:$PPORT/ctxkeeper/status" > "$1" 2>/dev/null
  systemctl --user stop ctx-keeper-proxy 2>/dev/null
  python3 - "$1" <<'PY'
import json, sys
try:
    for v in json.load(open(sys.argv[1])).values():
        print(f"   proxy: cuts {v['cuts']} (in place {v.get('inplace_cuts')}, failed attempts {v.get('inplace_failed')}, asked again {v.get('inplace_reasks')}), "
              f"messages archived {v['cut']}, recalls {v['recalls']}, full-rewrite notes failed {v['notes_failed']}, "
              f"notes calls: read {v.get('notes_prompt_tokens')} of which cached {v.get('notes_cached_tokens')}, written {v.get('notes_written_tokens')}, "
              f"restarts {v.get('restarts', 0)}, chars per token {v['ratio']}")
except Exception as exc:
    print("   proxy: no status:", exc)
PY
}
run_arm() {  # arm cap_seconds out_dir size sparse_args seed
  local arm=$1 cap=$2 od=$3 size=$4 sp=$5 seed=$6 t0=$SECONDS rc snp
  local tag="c13b-$arm-$((size/1000))k-s$seed" xk=""
  (( size >= 500000 )) && xk="emit_ctx_trajectory=false"
  if [[ $arm == X32* ]]; then start_proxy "$tag" || return 1; fi
  rm -f "$od/snap/$tag-answers.json" "$od/snap/$tag-answers.at" "$od/snap/$tag-answers.tmp"
  say "[$arm, $(basename "$od"), seed $seed] start (cap ${cap}s); MemAvailable $(avail) MiB; $(mline)"
  snap_loop "$od/snap" "$tag" & snp=$!
  timeout -s INT -k 180 "$cap" env OUT_DIR="$od" API_BASE="http://127.0.0.1:$PORT/v1" CTXKEEPER_BASE="http://127.0.0.1:$PPORT/v1" MODEL_NAME=qwen38-27b-fp8 SPARSE_ARGS="$sp" MAX_TOKENS=8192 \
      EXTRA_KWARGS="$xk" KINDS=sparse SEEDS="$seed" SIZES="$size" SUBSET=core ARMS="$arm" ./second-comparison.sh > "$od/arm-$arm-s$seed-c13b.out" 2>&1
  rc=$?
  kill "$snp" 2>/dev/null; wait "$snp" 2>/dev/null
  say "[$arm, $(basename "$od"), seed $seed] done rc=$rc in $(( (SECONDS-t0)/60 )) min $(( (SECONDS-t0)%60 )) s; MemAvailable $(avail) MiB; $(mline)"
  grep -h 'ledger score\|^!!!' "$od/arm-$arm-s$seed-c13b.out" | grep -v 'B32\|__sparse-memory.*EXC' | head -3 | cut -c1-200
  result_line "$od" "$arm" "$seed"
  if [[ $arm == X32* ]]; then stop_proxy "$od/proxy-status-$tag.json"; fi
  if (( rc == 124 || rc == 137 )); then
    say "[$arm] CUT at the time cap; last answers snapshot is $(( $(date +%s) - $(cat "$od/snap/$tag-answers.at" 2>/dev/null || echo 0) )) s old"
    for c in $(docker ps -q --filter name=sparse-); do docker rm -f "$c" >/dev/null 2>&1; done
    echo "$arm $od $seed $tag cut after $(( SECONDS - t0 )) s" >> "$O/CUT13B.txt"
  fi
  wait_idle || say "[$arm] server still busy after 3 min"
}
start_proxy_repair() {  # state tag, arm
  local nt=on; [[ ${2:-} == XR3* ]] && nt=off
  systemctl --user reset-failed ctx-keeper-proxy 2>/dev/null
  systemd-run --user --unit=ctx-keeper-proxy --collect -p WorkingDirectory=$LAB python3 tools/ctxkeeper/ctxkeeper.py \
    --upstream "http://127.0.0.1:$PORT" --port $PPORT --budget 32768 --reply-reserve 2048 --headroom 1024 --target-ratio 0.6 \
    --notes-thinking $nt --recite-when "$RECITE_RE_REPAIR" --notes-mode inplace --inplace-tokens 15000 --notes-checks off \
    --max-recalls 16 --state-dir "$O/proxy-state/$1" 2>&1 | tail -1
  for i in $(seq 1 30); do curl -fsS -m 3 "http://127.0.0.1:$PPORT/v1/models" >/dev/null 2>&1 && return 0; sleep 1; done
  say "proxy did not come up"; return 1
}
repair_result() {  # job_dir
  python3 - "$1" <<'PYEOF'
import glob, json, sys
g = glob.glob(sys.argv[1] + "/*/verifier/details.json")
if not g:
    print("   no verifier result"); sys.exit()
d = json.load(open(g[0]))
print(f"   RESULT fixed {d['fixed']}/{d['n']}  clean {d['clean']}/{d['n']}  rules " + "  ".join(f"{r} {v['kept']}/{v['applies']}" for r, v in d["rules"].items())
      + f"  tickets fetched {d.get('tickets_fetched')}  FIXES lines {d.get('fixes_lines')}  tests touched {len(d['tests_touched'])}  recipes wrongly listed {len(d['recipes_wrongly_listed'])}")
u = glob.glob(sys.argv[1] + "/*/agent/usage.json")
if u:
    u = json.load(open(u[0]))
    print(f"   calls {u.get('n_lm_calls')}, tokens written {u.get('completion_tokens')}, prompt {u.get('prompt_tokens')} cached {u.get('cached_tokens')}")
print(f"   stray unmarked lines {len(d.get('stray_unmarked_lines') or [])}, tickets delivered twice {d.get('tickets_delivered_twice')}")
a = d.get("audit")
if a:
    print(f"   AUDIT {a['right']}/{a['asked']} right ({a['lines']} lines written, {a['other_tickets']} for tickets not asked about)")
t = glob.glob(sys.argv[1] + "/*/agent/timing.json")
if t:
    import re
    cmds = [str(r.get("cmd") or "") for r in json.load(open(t[0]))]
    odd = [c for c in cmds if re.search(r"\bpip3?\b|\bcurl\b|\bwget\b|urllib|requests\.|_proxy|PIP_|tickets\.jsonl|/opt/repair", c, re.I)]
    print(f"   commands {len(cmds)}; commands that touch the network tools, the proxy settings or the ticket store: {len(odd)}" + ("" if not odd else " e.g. " + odd[0][:120]))
PYEOF
}
run_repair() {  # arm task cap
  local arm=$1 task=$2 cap=$3 t0=$SECONDS rc kind budget api="http://127.0.0.1:$PORT/v1" job="${1}__${2}"
  case $arm in
    XR*) kind=plain; budget=0; api="http://127.0.0.1:$PPORT/v1" ;;
    W32) kind=truncate; budget=32768 ;;
    C32) kind=summary; budget=32768 ;;
    A)   kind=plain; budget=0 ;;
  esac
  [[ -e $ODX/runs/jobs/$job ]] && { say "[$arm $task] already run, skipped"; return 0; }
  if [[ $arm == XR* ]]; then start_proxy_repair "c13b-$arm-$task" "$arm" || return 1; fi
  say "[$arm, $task] start (cap ${cap}s); MemAvailable $(avail) MiB; $(mline)"
  timeout -s INT -k 180 "$cap" env TASKS="$ODX/tasks/$task" JOB_NAME="$job" CONTEXT_BUDGET="$budget" ENABLE_THINKING=true MAX_TOKENS=8192 \
      MAX_STEPS="$MAX_STEPS_REPAIR" LM_CALL_CAP="$((3 * MAX_STEPS_REPAIR))" TASK_TEMPLATE=open_problems API_BASE="$api" MODEL_NAME=qwen38-27b-fp8 \
      ./run-context-job.sh "$kind" "$ODX/runs" > "$ODX/runs/$job.out" 2>&1
  rc=$?
  say "[$arm, $task] done rc=$rc in $(( (SECONDS-t0)/60 )) min $(( (SECONDS-t0)%60 )) s; MemAvailable $(avail) MiB; $(mline)"
  grep -h 'repair score' "$ODX/runs/jobs/$job"/*/verifier/test-stdout.txt 2>/dev/null | head -1 | sed 's/^/   /'
  repair_result "$ODX/runs/jobs/$job"
  if [[ $arm == XR* ]]; then stop_proxy "$ODX/runs/proxy-status-$job.json"; fi
  if (( rc == 124 || rc == 137 )); then
    say "[$arm] CUT at the time cap"
    for c in $(docker ps -q --filter name=repair-); do docker rm -f "$c" >/dev/null 2>&1; done
  fi
  wait_idle || say "[$arm] server still busy after 3 min"
}
ok_to_continue() {
  [[ -e $O/STOP-CAMPAIGN13B ]] && { say "stopped by STOP-CAMPAIGN13B"; return 1; }
  [[ -n $(faults) ]] && { say "GPU fault line in the kernel log; no further arms"; return 1; }
  server_up || { say "server is gone; no further arms (no restart)"; return 1; }
  return 0
}

done_lines=0 idle_since=0
while (( ready )); do
  ok_to_continue || break
  line=$(grep -vE '^\s*(#|$)' "$Q" | sed -n "$((done_lines+1))p")
  if [[ -z $line ]]; then
    (( idle_since == 0 )) && { idle_since=$SECONDS; say "queue empty after $done_lines runs; waiting up to ${IDLE_MAX}s for more lines in $Q"; }
    (( SECONDS - idle_since > IDLE_MAX )) && { say "no new line for ${IDLE_MAX}s; ending"; break; }
    sleep 10; continue
  fi
  idle_since=0; done_lines=$((done_lines+1))
  read -r arm stream seed cap <<< "$line"
  if [[ $stream == repair ]]; then run_repair "$arm" "repair-n40-s$seed" "${cap:-3600}"; continue; fi
  set -- $(stream_of "$stream" || echo ""); od=${1:-}; size=${2:-}
  if [[ -z $od ]]; then say "queue line '$line': unknown stream, skipped"; continue; fi
  stream_of "$stream" >/dev/null
  if [[ -z $(task_dir "$od" "$size" "$seed") ]]; then say "queue line '$line': no such task (tasks are generated before launch), skipped"; continue; fi
  if compgen -G "$od/runs/jobs/${arm}__sparse-memory-t*k-s$seed/*/verifier/reward.txt" >/dev/null; then say "queue line '$line': already run, skipped"; continue; fi
  run_arm "$arm" "${cap:-3600}" "$od" "$size" "$SP" "$seed"
done

systemctl --user stop ctx-keeper-proxy 2>/dev/null

# ---- server off, only when idle
say "stopping the server; MemAvailable $(avail) MiB"
if systemctl --user is-active --quiet ctx-fp8-tp2-server; then
  server_up && { wait_idle || say "server not idle after 3 min; stopping anyway"; }
  sleep 10
  touch "$SRV/STOP"
  for i in $(seq 1 40); do systemctl --user is-active --quiet ctx-fp8-tp2-server || break; sleep 5; done
  systemctl --user is-active --quiet ctx-fp8-tp2-server && systemctl --user stop ctx-fp8-tp2-server
fi
sleep 5
[[ -e $SRV/state.json ]] && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("server state:", d.get("status"), d.get("error"), "stop_confirmed", d.get("stop_confirmed"))' "$SRV/state.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && say "MEMORY GUARD fired: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["reason"])' "$SRV/MEMORY-GUARD.json")"
[[ -e $SRV/memory-guard.jsonl ]] && python3 - "$SRV/memory-guard.jsonl" <<'PY'
import json, sys
a = sorted(json.loads(l)["available"] / 2**30 for l in open(sys.argv[1]) if '"available"' in l)
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  1% {a[len(a)//100]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
for c in $(docker ps -q --filter name=sparse-); do say "removing leftover task container $c"; docker rm -f "$c" >/dev/null 2>&1; done
for c in $(docker ps -q --filter name=repair-); do say "removing leftover task container $c"; docker rm -f "$c" >/dev/null 2>&1; done

# ---- analysis (server is down)
for od in "$ODR" "$ODC" "$ODH" "$OD1M"; do
  [[ -d $od/runs/jobs ]] || continue
  "$PY" ./probe_analysis.py "$od" --json "$od/probe-analysis-campaign13b.json" > "$od/probe-analysis-campaign13b.txt" 2>&1 || say "analysis of $(basename "$od") rc=$?"
  say "$(basename "$od"): probes by distance and type, all arms so far"; sed -n '1,30p' "$od/probe-analysis-campaign13b.txt" | cut -c1-260
done
if [[ -e $O/CUT13B.txt ]]; then
  while read -r arm od seed tag _; do
    say "cut arm $arm (seed $seed), probes reached before the cut"
    "$PY" ./partial_grade.py "$(task_dir "$od" 0 "$seed")" "$od/snap/$tag-answers.json" --json "$od/snap/$tag-partial.json" 2>&1 | cut -c1-240
  done < "$O/CUT13B.txt"
fi

# ---- Gemma back, unless a fault was logged
F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
else
  say "kernel log clean since $START; restoring Gemma ($GEMMA_RECIPE)"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh "$GEMMA_RECIPE" 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
fi
say "campaign 13b complete"
