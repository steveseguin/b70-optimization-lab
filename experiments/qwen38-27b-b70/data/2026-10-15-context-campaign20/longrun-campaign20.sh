#!/usr/bin/env bash
# Campaign 20 (2026-10-15): well-known open-source coding agents on repair-n40-s2x through ctxkeeper 1.0.1
# (--recipe qwen), registered in the lab note before launch. Agents from tools/agentbench (pinned, as shipped, each in
# its own locked-down container); freeagent in the same harness is the control. One research server (the campaign-19
# settings); up to three agents at a time, each with its own fresh ctxkeeper; an agent starts only when host memory
# leaves room for it above the server's 1.6 GiB guard, and a watchdog stops the newest agent before the guard can
# fire. Gemma is stopped first and put back on its throughput recipe at the end.
#   AGENTS="freeagent goose" RUN=c20x ./longrun-campaign20.sh     (subset / rerun)
#   DRY=1 PORT=18390 SLOTS="18391 18392" RUN=dry ...            (scheduler test against tools/agentbench/fake_agent_server.py
#                                                                  already listening on PORT: no Gemma, no GPU server)
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
AB=$LAB/tools/agentbench
O=/mnt/fast-ai/bench-results/context-longrun-20261012
RUN=${RUN:-c20}
OUT=$O/$RUN
SRV=$O/server/tp2-w262144-$RUN
TASKDIR=$O/client-repair2/tasks/repair-n40-s2x
VENV=${VENV:-/mnt/fast-ai/venvs/ctxkeeper-1.0.1}
DRY=${DRY:-0}
PORT=${PORT:-18196}
read -ra SLOTS <<< "${SLOTS:-18200 18202 18204}"
TIME_LIMIT=${TIME_LIMIT:-5400}
GUARD_MIB=${GUARD_MIB:-1639}          # the server's B70_GUARD_MIN_AVAILABLE_GIB=1.6
MARGIN_MIB=${MARGIN_MIB:-300}          # kept free above the guard when an agent starts
WATCH_MIB=${WATCH_MIB:-1800}          # below this the newest agent is stopped
AGENTS=${AGENTS:-"freeagent goose mini-swe-agent qwen-code pi forgecode open-interpreter openhands hermes-agent kimi-code mistral-vibe cline opencode"}
# host memory each run may take (agent container non-file peak at a 4M history from the plumbing tests, rounded up,
# plus ~80 MiB for its ctxkeeper and bridge), and the container cap the agentbench README asks for
declare -A NEED=([freeagent]=180 [goose]=300 [mini-swe-agent]=400 [qwen-code]=450 [pi]=300 [forgecode]=200
  [open-interpreter]=260 [openhands]=500 [hermes-agent]=520 [kimi-code]=520 [mistral-vibe]=650 [cline]=850 [opencode]=1000)
declare -A CAP=([mistral-vibe]=1g [cline]=1g [opencode]=1536m)
(( DRY )) || export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
avail() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }
faults() { (( DRY )) && return 0; sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
server_up() { curl -fsS -m 10 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; }
up() { for i in $(seq 1 60); do curl -fsS -m 3 "$1/v1/models" >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }
wait_idle() {
  local r quiet=0
  for i in $(seq 1 60); do
    r=$(curl -fsS -m 5 "http://127.0.0.1:$PORT/metrics" 2>/dev/null | awk '/^vllm:num_requests_(running|waiting)/ {s+=$NF} END {print s+0}')
    if [[ $r == 0 ]]; then quiet=$((quiet+1)); (( quiet >= 2 )) && return 0; else quiet=0; fi
    sleep 3
  done
  return 1
}
proxy_status() {  # url file
  curl -fsS -m 5 "$1/ctxkeeper/status" > "$2" 2>/dev/null
  python3 - "$2" <<'PY'
import json, sys
try:
    for v in json.load(open(sys.argv[1])).values():
        print(f"   proxy: requests {v.get('requests')}, cuts {v['cuts']} (in place {v.get('inplace_cuts')}, failed {v.get('inplace_failed')}), "
              f"messages archived {v['cut']}, recalls {v['recalls']}, rules put back {v.get('rules_restored')}, chars per token {v['ratio']}")
except Exception as exc:
    print("   proxy: no status:", exc)
PY
}
repair_result() {  # job_dir
  python3 - "$1" <<'PYEOF'
import glob, json, sys
g = glob.glob(sys.argv[1] + "/*/verifier/details.json")
if not g:
    print("   no verifier result"); sys.exit()
d = json.load(open(g[0]))
print(f"   RESULT fixed {d['fixed']}/{d['n']}  clean {d['clean']}/{d['n']}  rules " + "  ".join(f"{r} {v['kept']}/{v['applies']}" for r, v in d["rules"].items())
      + f"  tickets fetched {d.get('tickets_fetched')}  FIXES lines {d.get('fixes_lines')}")
a = d.get("audit")
if a:
    print(f"   AUDIT {a['right']}/{a['asked']} right")
s = glob.glob(sys.argv[1] + "/*/agent/agentbench.json")
if s:
    s = json.load(open(s[0]))
    e, m, h = s.get("agent_exit") or {}, (s.get("memory") or {}).get("mib") or {}, s.get("history") or {}
    print(f"   run: agent exit {e.get('exit_code')} after {e.get('seconds')} s (timed out {e.get('timed_out')}), "
          f"requests {h.get('requests')}, whole history every time {h.get('whole_history_ok')}, "
          f"memory non-file peak {m.get('max_nonfile')} MiB")
PYEOF
}

mkdir -p "$OUT/proxy-state" "$OUT/runs"
say "campaign $RUN (agentbench through ctxkeeper 1.0.1) start; MemAvailable $(avail) MiB; agents: $AGENTS"
[[ "$("$VENV/bin/ctxkeeper" --version)" == "ctxkeeper 1.0.1" ]] || { say "ABORT: $VENV has no ctxkeeper 1.0.1"; exit 2; }
[[ -e $TASKDIR/tests/spec.json ]] || { say "ABORT: no task"; exit 2; }
for a in $AGENTS; do
  docker image inspect "agentbench-$a:repair-n40-s2x" >/dev/null 2>&1 || { say "ABORT: no image for $a"; exit 2; }
  [[ -n ${NEED[$a]:-} ]] || { say "ABORT: no memory figure for $a"; exit 2; }
done
(( DRY )) || { [[ -e $SRV ]] && { say "ABORT: $SRV already exists"; exit 2; }; }
for p in $( (( DRY )) || echo $PORT) "${SLOTS[@]}"; do ss -tln | grep -q ":$p " && { say "ABORT: port $p is in use"; exit 2; }; done
[[ -n $(docker ps -q --filter name=fp8-tp) ]] && { say "ABORT: an fp8 container is already running"; exit 2; }
[[ -n $(docker ps -q --filter name=agentbench-) ]] && { say "ABORT: an agentbench container is already running"; exit 2; }
[[ -n $(systemctl --user list-units --state=active --no-legend 'dl-*' 2>/dev/null) ]] && { say "ABORT: a download unit is running"; exit 2; }
systemctl --user is-active --quiet lfm25-srv && { say "ABORT: the LFM2.5 server is running"; exit 2; }

ready=0
if (( DRY )); then
  server_up && ready=1 && say "DRY: scripted model on :$PORT"
else
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

# ---- the research server (campaign-19 settings)
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
  [[ -n $(faults) ]] && { say "GPU fault line during server start"; break; }
  sleep 15
done
fi

# ---- the agents: a queue, up to ${#SLOTS[@]} at a time, each started only with memory to spare
set +u   # bash treats an empty associative array as unset under nounset
declare -A SLOT_JOB=() SLOT_PID=() SLOT_AGENT=() SLOT_T0=()
queue=($AGENTS)
stopping=0
finish_slot() {  # port
  local p=$1 job=${SLOT_JOB[$1]} a=${SLOT_AGENT[$1]}
  wait "${SLOT_PID[$p]}" 2>/dev/null; local rc=$?
  say "[$a] done rc=$rc in $(( (SECONDS-${SLOT_T0[$p]})/60 )) min $(( (SECONDS-${SLOT_T0[$p]})%60 )) s; MemAvailable $(avail) MiB"
  repair_result "$OUT/runs/jobs/$job"
  proxy_status "http://127.0.0.1:$p" "$OUT/$job-proxy-status.json"
  systemctl --user stop "ctxk-$p" 2>/dev/null
  unset "SLOT_JOB[$p]" "SLOT_PID[$p]" "SLOT_AGENT[$p]" "SLOT_T0[$p]"
}
if (( ready )); then
  while (( ${#queue[@]} > 0 || ${#SLOT_JOB[@]} > 0 )); do
    # finished runs free their slot
    for p in "${!SLOT_PID[@]}"; do kill -0 "${SLOT_PID[$p]}" 2>/dev/null || finish_slot "$p"; done
    # health: server, kernel log, host memory
    if ! server_up || [[ -n $(faults) ]]; then
      (( stopping )) || say "server down or GPU fault line: no new agents; stopping the running ones"
      stopping=1; queue=()
      for p in "${!SLOT_JOB[@]}"; do docker stop -t 20 "agentbench-${SLOT_JOB[$p]}" >/dev/null 2>&1; done
    fi
    m=$(avail)
    if (( m < WATCH_MIB && ${#SLOT_JOB[@]} > 0 )); then
      newest=; for p in "${!SLOT_T0[@]}"; do [[ -z $newest || ${SLOT_T0[$p]} -gt ${SLOT_T0[$newest]} ]] && newest=$p; done
      say "WATCHDOG: MemAvailable $m MiB < $WATCH_MIB; stopping the newest agent ${SLOT_AGENT[$newest]} (void: host memory)"
      echo "${SLOT_AGENT[$newest]} $(date +%T) MemAvailable $m" >> "$OUT/watchdog-stops.txt"
      docker stop -t 20 "agentbench-${SLOT_JOB[$newest]}" >/dev/null 2>&1
      sleep 30; continue
    fi
    # start the next agent if a slot and the memory are free
    if (( ${#queue[@]} > 0 && ! stopping )); then
      a=${queue[0]}
      free_port=; for p in "${SLOTS[@]}"; do [[ -z ${SLOT_JOB[$p]:-} ]] && { free_port=$p; break; }; done
      if [[ -n $free_port ]]; then
        if (( m >= GUARD_MIB + MARGIN_MIB + NEED[$a] )); then
          queue=("${queue[@]:1}")
          job="AB-${a}__repair-n40-s2x"
          systemctl --user reset-failed "ctxk-$free_port" 2>/dev/null
          systemd-run --user --unit="ctxk-$free_port" --collect "$VENV/bin/ctxkeeper" --upstream "http://127.0.0.1:$PORT" \
            --recipe qwen --port "$free_port" --state-dir "$OUT/proxy-state/$job" >/dev/null 2>&1
          if up "http://127.0.0.1:$free_port"; then
            say "[$a] start on proxy :$free_port (cap ${CAP[$a]:-768m}, time limit $TIME_LIMIT s); MemAvailable $m MiB"
            AGENT_MEM=${CAP[$a]:-768m} MODEL_NAME=qwen38-27b-fp8 timeout -s INT -k 300 $((TIME_LIMIT + 900)) \
              "$AB/run-agent-job.sh" "$a" "$TASKDIR" "$OUT/runs" "$job" "http://127.0.0.1:$free_port/v1" "$TIME_LIMIT" \
              > "$OUT/$job.out" 2>&1 &
            SLOT_PID[$free_port]=$!; SLOT_JOB[$free_port]=$job; SLOT_AGENT[$free_port]=$a; SLOT_T0[$free_port]=$SECONDS
            sleep 60; continue          # let it reach its working size before the next memory check
          else
            say "[$a] its proxy did not come up; skipped"; systemctl --user stop "ctxk-$free_port" 2>/dev/null
          fi
        elif (( ${#SLOT_JOB[@]} == 0 )); then
          queue=("${queue[@]:1}")
          say "[$a] NOT RUN: MemAvailable $m MiB leaves no room for it ($((GUARD_MIB + MARGIN_MIB + NEED[$a])) needed) even alone"
        fi
      fi
    fi
    sleep 15
  done
fi
for p in "${SLOTS[@]}"; do systemctl --user stop "ctxk-$p" 2>/dev/null; done
(( DRY )) && { say "DRY run $RUN complete"; exit 0; }

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
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
for c in $(docker ps -q --filter name=agentbench-); do say "removing leftover agent container $c"; docker rm -f "$c" >/dev/null 2>&1; done

# ---- Gemma back on its throughput recipe (both cards), unless a fault was logged
F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
  exit 1
fi
say "kernel log clean since $START; Gemma back on its throughput recipe"
cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
F=$(faults); [[ -n $F ]] && { say "GPU FAULT LINES after the Gemma restart:"; echo "$F" | head -10 | cut -c1-220; }
say "campaign $RUN complete"
