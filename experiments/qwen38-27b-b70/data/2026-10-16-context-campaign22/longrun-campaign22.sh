#!/usr/bin/env bash
# Campaign 22 (2026-10-16, registered in the lab note before any run): Qwen3.8-27B FP8 on ONE card (card 0, 26,624-token
# window) with ctxkeeper, and a different, smaller model as the keeper: LFM2.5-24B-A2B Q8_0 (package v4 build, about
# 2B active parameters) on card 1 writes the notes. LFM2.5 is loaded first (its file streams through host memory),
# then the one-card Qwen server. Every proxy is tools/ctxkeeper/ctxkeeper.py at 1.1.0.dev0 with --log-calls.
# Queue lines: "ARM KIND SEED CAP_SECONDS", KIND = smoke | rules (240K rules stream) | 1m | repair.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
O=/mnt/fast-ai/bench-results/context-longrun-20261016
RUN=${RUN:-c22}
SRV=$O/server/tp1-w26624-$RUN
Q=${QUEUE:-$O/QUEUE22.txt}
PORT=18196
PPORT=18200
KPORT=18110
KEEPER_MODEL=lfm25-24b-a2b
LFM_BUILD=/home/steve/src/llama.cpp-lfm25-pkgcheck-v4-20261015/build
LFM_MODEL=/mnt/fast-ai/llm-models/lfm25-24b-a2b-q8-gguf
LFM_CTX=${LFM_CTX:-65536}
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
GEMMA_RECIPE=${GEMMA_RECIPE:-throughput}
IDLE_MAX=${IDLE_MAX:-600}
ODR=/mnt/fast-ai/bench-results/context-longrun-20261010/client-rules
OD1M=/mnt/fast-ai/bench-results/context-longrun-20261011/client-1m
ODX=/mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2
SP240="--density 3 --words --probes-every 25 --probes-k 3 --rules"
SP1M="--density 3 --words --probes-every 20 --probes-k 5 --rules"
MAX_STEPS_REPAIR=900
THINK_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)|^PROBE:|STREAM END|NOT RUN|Traceback|\(exit_code=[1-9-]'
RECITE_RE='(?m)^(?:ASK \S+?:|QUERY \S+|GET \S+)'
UNTIL_RE='(?m)^ITEM \d+/\d+ \(UPDATE\)'
SCAN_RE='(?m)^ITEM \d+/\d+ \(UPDATE\)'
LABEL_RE='(?m)^ITEM (\d+)/'
RECITE_RE_REPAIR='(?m)^TICKET \d+/\d+ \((BUG|NOTICE)\)'
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
avail() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
server_up() { curl -fsS -m 10 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; }
wait_idle() {  # no request running or waiting on the server for two polls in a row (at most 3 min)
  local r quiet=0
  for i in $(seq 1 60); do
    r=$(curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" 2>/dev/null | awk '/^vllm:num_requests_(running|waiting)/ {s+=$NF} END {print s+0}')
    if [[ $r == 0 ]]; then quiet=$((quiet+1)); (( quiet >= 2 )) && return 0; else quiet=0; fi
    sleep 3
  done
  return 1
}
mline() {
  curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" 2>/dev/null | awk '/^vllm:prefix_cache_queries_total/ {q=$NF} /^vllm:prefix_cache_hits_total/ {h=$NF} /^vllm:generation_tokens_total/ {g=$NF} END {printf "server totals: prompt %d cached %d generated %d", q, h, g}'
}

# ---- arms. The one-card server refuses a request whose prompt + max_tokens passes 26,624; the client asks for 8,192
# reply tokens, so the proxy keeps the view to 26,624 - 8,192 (reply reserve) and caps notes replies at 6,144.
# O* = the model keeps its own notes (one card, nothing else); L* = LFM2.5 on card 1 writes them; *d = in the
# background (defer); *p = long tool results cut down for the keeper (--notes-prepass 2000, repair task only).
arm_window() {  # arm -> "budget inplace_tokens"
  case $1 in O1 | L1 | L1d | O1r | L1r | L1rp | L1rd | SL) echo "26624 9000" ;; *) return 1 ;; esac
}
arm_async() {  # arm -> keeper options
  local k="--notes-upstream http://127.0.0.1:$KPORT --notes-model $KEEPER_MODEL"
  case $1 in L1 | L1r) echo "$k" ;; L1d | L1rd | SL) echo "$k --notes-async defer" ;; L1rp) echo "$k --notes-prepass 2000" ;; *) echo "" ;; esac
}
start_proxy() {  # tag arm kind
  local tag=$1 arm=$2 kind=$3 w b i fl=()
  w=$(arm_window "$arm") || { say "unknown arm $arm"; return 1; }
  read -r b i <<< "$w"
  case $kind in
    rules | 1m) fl=(--reply-reserve 2048 --headroom 1024 --target-ratio 0.6 --notes-thinking on --effort medium
                    --think-when "$THINK_RE" --think-until "$UNTIL_RE" --recite-when "$RECITE_RE" --notes-mode inplace
                    --notes-checks near --max-recalls 16 --notes-scan "$SCAN_RE" --recall-label "$LABEL_RE" --recall-unit item) ;;
    repair)     fl=(--reply-reserve 2048 --headroom 1024 --target-ratio 0.6 --notes-thinking off --effort medium
                    --recite-when "$RECITE_RE_REPAIR" --notes-mode inplace --notes-checks off --max-recalls 16) ;;
    smoke)      fl=(--recipe qwen) ;;
  esac
  systemctl --user reset-failed ctx-keeper-proxy 2>/dev/null
  # shellcheck disable=SC2046
  systemd-run --user --unit=ctx-keeper-proxy --collect -p WorkingDirectory=$LAB python3 tools/ctxkeeper/ctxkeeper.py \
    --upstream "http://127.0.0.1:$PORT" --port $PPORT "${fl[@]}" --budget "$b" --inplace-tokens "$i" --reply-reserve 8192 \
    --notes-max-tokens 6144 $(arm_async "$arm") \
    --log-calls --state-dir "$O/proxy-state/$tag" 2>&1 | tail -1
  for k in $(seq 1 30); do curl -fsS -m 3 "http://127.0.0.1:$PPORT/v1/models" >/dev/null 2>&1 && return 0; sleep 1; done
  say "proxy did not come up"; journalctl --user -u ctx-keeper-proxy --no-pager -n 5 -o cat; return 1
}
stop_proxy() {  # status_file since
  curl -fsS -m 5 "http://127.0.0.1:$PPORT/ctxkeeper/status" > "$1" 2>/dev/null
  systemctl --user stop ctx-keeper-proxy 2>/dev/null
  python3 - "$1" <<'PY'
import json, sys
try:
    for v in json.load(open(sys.argv[1])).values():
        print(f"   proxy: cuts {v['cuts']} (in place {v.get('inplace_cuts')}, failed {v.get('inplace_failed')}, asked again {v.get('inplace_reasks')}), "
              f"archived {v['cut']}, recalls {v['recalls']}, full-rewrite failed {v['notes_failed']}, notes read {v.get('notes_prompt_tokens')} "
              f"cached {v.get('notes_cached_tokens')} written {v.get('notes_written_tokens')}; background started {v.get('async_started', 0)} "
              f"applied {v.get('async_applied', 0)} discarded {v.get('async_discarded', 0)} waited {v.get('async_wait_s', 0)} s; "
              f"upstream {v.get('upstream_s')} s (background {v.get('background_s', 0)} s); restarts {v.get('restarts', 0)}")
except Exception as exc:
    print("   proxy: no status:", exc)
PY
  proxy_errors "$2" | head -5 | sed 's/^/   proxy log: /'
}
proxy_errors() { journalctl --user -u ctx-keeper-proxy --since "$1" --no-pager -o cat 2>/dev/null | grep -E "Traceback|Error|exception"; }
calls_line() {  # state dir: what calls.jsonl says (the largest single call is the window the run really needed)
  python3 - "$1" <<'PY'
import glob, json, sys
rows = []
for f in glob.glob(sys.argv[1] + "/*/calls.jsonl"):
    rows += [json.loads(l) for l in open(f) if l.strip()]
if not rows:
    print("   calls: none logged"); sys.exit()
by = {}
for r in rows:
    k = r.get("kind", "?") + (" (background)" if r.get("background") else "")
    a = by.setdefault(k, [0, 0.0, 0, 0, 0]); a[0] += 1; a[1] += r.get("s") or 0
    a[2] += r.get("prompt") or 0; a[3] += r.get("cached") or 0; a[4] += r.get("written") or 0
peak = max((r.get("prompt") or 0) + (r.get("written") or 0) for r in rows)
print("   calls: " + "; ".join(f"{k} {a[0]} calls {a[1]:.0f} s read {a[2]} cached {a[3]} written {a[4]}" for k, a in by.items())
      + f"; largest call (read + written) {peak} tokens")
PY
}
snap_loop() {  # snap_dir tag: copy /app/answers.json out of the task container every 2 minutes
  local sd=$1 tag=$2 c
  while :; do
    sleep 120
    c=$(docker ps --filter name=sparse- --format '{{.Names}}' | head -1)
    [[ -n $c ]] && docker cp "$c:/app/answers.json" "$sd/$tag-answers.json" >/dev/null 2>&1 && date +%s > "$sd/$tag-answers.at"
  done
}
stream_result() {  # job dir
  python3 - "$1" <<'PY'
import glob, json, sys
g = glob.glob(sys.argv[1] + "/*/")
if not g:
    print("   no trial directory"); sys.exit()
t = g[0]
def load(name):
    try:
        return json.load(open(t + name))
    except Exception:
        return None
d, u = load("verifier/details.json"), load("agent/usage.json")
if d:
    print(f"   RESULT {d.get('correct')}/{d.get('n')} void={d.get('void')} violations={len(d.get('violations') or [])} counts={d.get('counts')}")
if u:
    print(f"   client: calls {u.get('n_lm_calls')} (main loop {u.get('total_iters')}), written {u.get('completion_tokens')}, prompt {u.get('prompt_tokens')} cached {u.get('cached_tokens')}")
PY
}
repair_result() {  # job dir
  python3 - "$1" <<'PY'
import glob, json, sys
g = glob.glob(sys.argv[1] + "/*/verifier/details.json")
if not g:
    print("   no verifier result"); sys.exit()
d = json.load(open(g[0]))
a = d.get("audit") or {}
print(f"   RESULT fixed {d['fixed']}/{d['n']}  clean {d['clean']}/{d['n']}  rules " + "  ".join(f"{r} {v['kept']}/{v['applies']}" for r, v in d["rules"].items())
      + f"  tests touched {len(d['tests_touched'])}  AUDIT {a.get('right')}/{a.get('asked')}")
PY
}

run_line() {  # arm kind seed cap
  local arm=$1 kind=$2 seed=$3 cap=$4 t0=$SECONDS rc snp="" tag="$RUN-$1-$2-s$3" job tasks runs xk="" sp="" since
  since=$(date '+%F %T')
  case $kind in
    smoke)
      start_proxy "$tag" "$arm" smoke || return 1
      say "[$arm smoke] start; MemAvailable $(avail) MiB; $(mline)"
      timeout -s INT -k 60 "$cap" python3 "$LAB/tools/ctxkeeper/examples/long_chat.py" --base-url "http://127.0.0.1:$PPORT/v1" \
        --tokens 60000 --report-tokens 1000 --extra-body '{"chat_template_kwargs": {"enable_thinking": false}}' > "$O/$tag.out" 2>&1
      rc=$?
      say "[$arm smoke] done rc=$rc in $((SECONDS-t0)) s"; tail -6 "$O/$tag.out" | sed 's/^/   /'
      wait_idle || say "server still busy after 3 min"
      stop_proxy "$O/proxy-status-$tag.json" "$since"; calls_line "$O/proxy-state/$tag"
      # the smoke test checks the separate-keeper path, not the model: it fails on a proxy error, a client that did not
      # finish, or no notes from the keeper applied (a missed question alone is reported but does not fail it)
      local applied
      applied=$(python3 -c 'import json,sys; print(sum(v.get("async_applied", 0) for v in json.load(open(sys.argv[1])).values()))' "$O/proxy-status-$tag.json" 2>/dev/null || echo 0)
      if ! grep -q "checks passed" "$O/$tag.out" || (( applied < 1 )) || [[ -n $(proxy_errors "$since") ]]; then
        say "SMOKE FAILED (background notes applied: $applied): the LFM2.5 keeper arms are skipped"; NO_ASYNC=1
      fi
      return 0 ;;
    rules) tasks=$ODR/tasks/sparse-memory/sparse-memory-t240k-s$seed; sp=$SP240; job="${arm}__sparse-memory-t240k-s$seed"; runs=$O/runs/rules ;;
    1m)    tasks=$OD1M/tasks/sparse-memory/sparse-memory-t1000k-s$seed; sp=$SP1M; job="${arm}__sparse-memory-t1000k-s$seed"; runs=$O/runs/1m; xk="emit_ctx_trajectory=false" ;;
    repair) tasks=$ODX/tasks/repair-n40-s$seed; job="${arm}__repair-n40-s$seed"; runs=$O/runs/repair ;;
    *) say "unknown kind $kind"; return 1 ;;
  esac
  [[ $arm == L* && ${NO_ASYNC:-0} == 1 ]] && { say "[$arm] skipped (the smoke test failed)"; return 0; }
  [[ -e $runs/jobs/$job ]] && { say "[$job] already run, skipped"; return 0; }
  mkdir -p "$runs" "$O/snap"
  start_proxy "$tag" "$arm" "$kind" || return 1
  say "[$job] start (cap ${cap}s); MemAvailable $(avail) MiB; $(mline)"
  if [[ $kind == repair ]]; then
    timeout -s INT -k 180 "$cap" env TASKS="$tasks" JOB_NAME="$job" CONTEXT_BUDGET=0 ENABLE_THINKING=true MAX_TOKENS=8192 \
        MAX_STEPS="$MAX_STEPS_REPAIR" LM_CALL_CAP="$((3 * MAX_STEPS_REPAIR))" TASK_TEMPLATE=open_problems \
        API_BASE="http://127.0.0.1:$PPORT/v1" MODEL_NAME=qwen38-27b-fp8 ./run-context-job.sh plain "$runs" > "$runs/$job.out" 2>&1
    rc=$?
  else
    snap_loop "$O/snap" "$tag" & snp=$!
    timeout -s INT -k 180 "$cap" env TASKS="$tasks" JOB_NAME="$job" CONTEXT_BUDGET=0 DROP_OLD_THINKING=0 ENABLE_THINKING=true \
        MAX_TOKENS=8192 TEMPERATURE=0 TASK_TEMPLATE=open_problems API_BASE="http://127.0.0.1:$PPORT/v1" MODEL_NAME=qwen38-27b-fp8 \
        EXTRA_KWARGS="$xk" ./run-context-job.sh plain "$runs" > "$runs/$job.out" 2>&1
    rc=$?
    kill "$snp" 2>/dev/null; wait "$snp" 2>/dev/null
  fi
  say "[$job] done rc=$rc in $(( (SECONDS-t0)/60 )) min $(( (SECONDS-t0)%60 )) s; MemAvailable $(avail) MiB; $(mline)"
  if [[ $kind == repair ]]; then
    grep -h 'repair score' "$runs/jobs/$job"/*/verifier/test-stdout.txt 2>/dev/null | head -1 | sed 's/^/   /'
    repair_result "$runs/jobs/$job"
  else
    grep -h 'ledger score' "$runs/jobs/$job"/*/verifier/test-stdout.txt 2>/dev/null | head -1 | cut -c1-200 | sed 's/^/   /'
    stream_result "$runs/jobs/$job"
    "$PY" ./summarize_results.py --brief --check "$runs/jobs/$job" > "$runs/$job.check" 2>&1 || say "[$job] summarize_results --check flagged the run (see $runs/$job.check)"
  fi
  if (( rc == 124 || rc == 137 )); then
    say "[$job] CUT at the time cap"
    for c in $(docker ps -q --filter name=sparse-) $(docker ps -q --filter name=repair-); do docker rm -f "$c" >/dev/null 2>&1; done
    echo "$arm $kind $seed $tag cut after $(( SECONDS - t0 )) s" >> "$O/CUT22.txt"
  fi
  wait_idle || say "[$job] server still busy after 3 min"
  stop_proxy "$O/proxy-status-$tag.json" "$since"
  calls_line "$O/proxy-state/$tag"
}
PY=/mnt/fast-ai/venvs/clm/bin/python

say "campaign 22 ($RUN) start; queue $Q ($(grep -cvE '^\s*(#|$)' "$Q" 2>/dev/null || echo 0) lines); MemAvailable $(avail) MiB"
[[ -s $Q ]] || { say "ABORT: the queue file is missing or empty"; exit 2; }
[[ -e $SRV ]] && { say "ABORT: $SRV already exists"; exit 2; }
for p in $PORT $PPORT $KPORT; do ss -tln | grep -q ":$p " && { say "ABORT: port $p is in use"; exit 2; }; done
[[ -n $(docker ps -q --filter name=fp8-tp) ]] && { say "ABORT: an fp8 container is already running"; exit 2; }
[[ -n $(docker ps -q --filter name=sparse-)$(docker ps -q --filter name=repair-) ]] && { say "ABORT: a task container is already running"; exit 2; }
[[ -n $(systemctl --user list-units --state=active --no-legend 'dl-*' 2>/dev/null) ]] && { say "ABORT: a download unit is running"; exit 2; }
for u in lfm25-srv lfm25-pkg-srv lfm25-keeper-srv ctx-keeper-proxy; do systemctl --user is-active --quiet $u && { say "ABORT: $u is running"; exit 2; }; done
[[ "$(python3 "$LAB/tools/ctxkeeper/ctxkeeper.py" --version)" == "ctxkeeper 1.1.0.dev0" ]] || { say "ABORT: tools/ctxkeeper is not 1.1.0.dev0"; exit 2; }
cd "$CTX" || exit 2
while read -r arm kind seed cap; do
  [[ -z $arm || $arm == \#* ]] && continue
  arm_window "$arm" >/dev/null || { say "ABORT: unknown arm '$arm'"; exit 2; }
  case $kind in
    smoke) ;;
    rules) [[ -e $ODR/tasks/sparse-memory/sparse-memory-t240k-s$seed/tests ]] || { say "ABORT: no rules task s$seed"; exit 2; } ;;
    1m) [[ -e $OD1M/tasks/sparse-memory/sparse-memory-t1000k-s$seed/tests ]] || { say "ABORT: no 1M task s$seed"; exit 2; } ;;
    repair) [[ -e $ODX/tasks/repair-n40-s$seed/tests/spec.json ]] || { say "ABORT: no repair task s$seed"; exit 2; } ;;
    *) say "ABORT: unknown kind '$kind'"; exit 2 ;;
  esac
done < "$Q"
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

# ---- LFM2.5 keeper on card 1 first (the package's exact fast mode; its file streams through host memory, so it
# loads before the Qwen server is there to be squeezed)
mkdir -p "$O/keeper-$RUN"
for i in $(seq 1 30); do [[ -z $(ss -Htan "( sport = :$KPORT or dport = :$KPORT )") ]] && break; sleep 5; done
systemctl --user reset-failed lfm25-keeper-srv 2>/dev/null
systemd-run --user --unit=lfm25-keeper-srv --collect -p WorkingDirectory=$LAB -E BUILD_DIR=$LFM_BUILD -E MODEL_DIR=$LFM_MODEL \
  -E GPU=1 -E PORT=$KPORT -E CTX=$LFM_CTX -E ALIAS=$KEEPER_MODEL \
  bash -c "exec $LAB/repro/lfm25-24b-a2b-q8-b70/serve.sh fast > $O/keeper-$RUN/server-fast.log 2>&1" 2>&1 | tail -1
kready=0
for i in $(seq 1 120); do
  curl -fsS -m 2 "http://127.0.0.1:$KPORT/v1/models" >/dev/null 2>&1 && { kready=1; break; }
  systemctl --user is-active --quiet lfm25-keeper-srv || break
  sleep 2
done
(( kready )) || { say "ABORT: the LFM2.5 keeper did not come up"; tail -5 "$O/keeper-$RUN/server-fast.log"; systemctl --user stop lfm25-keeper-srv 2>/dev/null; GEMMA_ONLY=1; }
say "LFM2.5 keeper ready=$kready; MemAvailable $(avail) MiB"
sleep 20
say "after 20 s: MemAvailable $(avail) MiB"

# ---- the one-card Qwen server on card 0 (B70_ALLOW_BUSY_RENDER: card 1 is busy on purpose)
ready=0
if (( kready )); then
for i in $(seq 1 30); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 5; done
systemctl --user reset-failed ctx-fp8-tp1-server 2>/dev/null
systemd-run --user --unit=ctx-fp8-tp1-server --collect -p WorkingDirectory=$LAB -E B70_GUARD_MIN_AVAILABLE_GIB=1.6 -E B70_ALLOW_BUSY_RENDER=1 \
  python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py --out "$SRV" --port $PORT --gpu 0 --tp 1 \
  --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800 \
  --mem 0.975 --max-model-len 26624 --batched 832 --seqs 1 --mtp 5 --draft-int4 --cpu-embed --fa-verify-rows \
  --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt \
  --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
  --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 \
  --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
  --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
  --serve-arg=--prefix-cache-retention-interval=13312 --serve-arg=--enable-auto-tool-choice \
  --serve-arg=--tool-call-parser=qwen3_coder --serve-arg=--reasoning-parser=qwen3 2>&1 | tail -1
fi
for i in $( (( kready )) && seq 1 120); do
  if server_up; then ready=1; say "server ready after ~$((i*15)) s; MemAvailable $(avail) MiB"; break; fi
  systemctl --user is-active --quiet ctx-fp8-tp1-server || { say "server unit ended before ready"; break; }
  [[ -n $(faults) ]] && { say "GPU fault line during server start"; break; }
  sleep 15
done

ok_to_continue() {
  [[ -e $O/STOP-CAMPAIGN22 ]] && { say "stopped by STOP-CAMPAIGN22"; return 1; }
  [[ -n $(faults) ]] && { say "GPU fault line in the kernel log; no further arms"; return 1; }
  server_up || { say "server is gone; no further arms (no restart)"; return 1; }
  curl -fsS -m 10 "http://127.0.0.1:$KPORT/v1/models" >/dev/null 2>&1 || { say "the LFM2.5 keeper is gone; no further arms"; return 1; }
  local room=$(( $(avail) - 1638 ))
  (( room < 256 )) && { say "room beside the server is ${room} MiB, under the 256 MiB task-container cap; no further arms"; return 1; }
  return 0
}
NO_ASYNC=0 done_lines=0 idle_since=0
while (( ready )); do
  ok_to_continue || break
  line=$(grep -vE '^\s*(#|$)' "$Q" | sed -n "$((done_lines+1))p")
  if [[ -z $line ]]; then
    (( idle_since == 0 )) && { idle_since=$SECONDS; say "queue empty after $done_lines lines; waiting up to ${IDLE_MAX}s for more lines in $Q"; }
    (( SECONDS - idle_since > IDLE_MAX )) && { say "no new line for ${IDLE_MAX}s; ending"; break; }
    sleep 10; continue
  fi
  idle_since=0; done_lines=$((done_lines+1))
  read -r arm kind seed cap <<< "$line"
  arm_window "$arm" >/dev/null || { say "queue line '$line': unknown arm, skipped"; continue; }
  run_line "$arm" "$kind" "${seed:-0}" "${cap:-3600}"
done
systemctl --user stop ctx-keeper-proxy 2>/dev/null

# ---- server off, only when idle (then the keeper)
say "stopping the server; MemAvailable $(avail) MiB"
if systemctl --user is-active --quiet ctx-fp8-tp1-server; then
  server_up && { wait_idle || say "server not idle after 3 min; stopping anyway"; }
  sleep 10
  touch "$SRV/STOP"
  for i in $(seq 1 40); do systemctl --user is-active --quiet ctx-fp8-tp1-server || break; sleep 5; done
  systemctl --user is-active --quiet ctx-fp8-tp1-server && systemctl --user stop ctx-fp8-tp1-server
fi
sleep 5
systemctl --user stop lfm25-keeper-srv 2>/dev/null
for i in $(seq 1 30); do pgrep -f "llama-server.*--port $KPORT" >/dev/null || break; sleep 2; done
[[ -e $SRV/state.json ]] && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("server state:", d.get("status"), d.get("error"), "stop_confirmed", d.get("stop_confirmed"))' "$SRV/state.json"
[[ -e $SRV/MEMORY-GUARD.json ]] && say "MEMORY GUARD fired: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["reason"])' "$SRV/MEMORY-GUARD.json")"
[[ -e $SRV/memory-guard.jsonl ]] && python3 - "$SRV/memory-guard.jsonl" <<'PY'
import json, sys
a = sorted(json.loads(l)["available"] / 2**30 for l in open(sys.argv[1]) if '"available"' in l)
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  1% {a[len(a)//100]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
for c in $(docker ps -q --filter name=sparse-) $(docker ps -q --filter name=repair-); do say "removing leftover task container $c"; docker rm -f "$c" >/dev/null 2>&1; done
if [[ -e $O/CUT22.txt ]]; then
  while read -r arm kind seed tag _; do
    [[ $kind == rules ]] && td=$ODR/tasks/sparse-memory/sparse-memory-t240k-s$seed || td=$OD1M/tasks/sparse-memory/sparse-memory-t1000k-s$seed
    [[ $kind == repair ]] && continue
    say "cut arm $arm ($kind s$seed), questions reached before the cut"
    "$PY" ./partial_grade.py "$td" "$O/snap/$tag-answers.json" --json "$O/snap/$tag-partial.json" 2>&1 | cut -c1-240
  done < "$O/CUT22.txt"
fi

# ---- Gemma back, unless a fault was logged
F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
else
  say "kernel log clean since $START; restoring Gemma ($GEMMA_RECIPE)"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh "$GEMMA_RECIPE" 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
fi
say "campaign 22 complete"
