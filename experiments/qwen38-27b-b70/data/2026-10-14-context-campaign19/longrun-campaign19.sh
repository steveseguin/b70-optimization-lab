#!/usr/bin/env bash
# Campaign 19 (2026-10-14): the release gate for ctxkeeper 1.0.0, registered in the lab note before launch.
# Runs what the README tells a user to run, installed the way a user installs it:
#   G1 freeagent + `ctxkeeper --recipe qwen` (pip-installed from the public repo, nothing else) on repair-n40-s2x
#   G2 examples/long_chat.py (300K tokens, beyond the server's 262K) through the Docker image, --recipe qwen
#   G3 the README's OpenAI SDK snippet (plain, tool call, streaming) through the pip-installed proxy
#   G4 after the FP8 server is down: long_chat.py through `--recipe agent` against Gemma 4 26B on llama.cpp
#      (the LAN service on its `balanced` recipe, 16K per request); then Gemma back on `throughput`.
# Rerun (c19b, after the first G1 was voided by the server's memory guard): RUN=c19b G1JOB=G1b__repair-n40-s2x SKIP_G4=1
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
O=/mnt/fast-ai/bench-results/context-longrun-20261012
RUN=${RUN:-c19}
OUT=$O/$RUN
SRV=$O/server/tp2-w262144-$RUN
ODX=$O/client-repair2
VENV=${VENV:-/mnt/fast-ai/venvs/ctxkeeper-1.0.0}
IMG=ctxkeeper:1.0.0
PORT=18196
PPORT=18200
DPORT=18201
TASK=repair-n40-s2x
G1JOB=${G1JOB:-G1__$TASK}
SKIP_G4=${SKIP_G4:-0}
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
avail() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
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
proxy_status() {  # url file: keep the proxy's counters and print them
  curl -fsS -m 5 "$1/ctxkeeper/status" > "$2" 2>/dev/null
  python3 - "$2" <<'PY'
import json, sys
try:
    for v in json.load(open(sys.argv[1])).values():
        print(f"   proxy: cuts {v['cuts']} (in place {v.get('inplace_cuts')}, failed {v.get('inplace_failed')}, asked again {v.get('inplace_reasks')}), "
              f"messages archived {v['cut']}, recalls {v['recalls']}, notes read {v.get('notes_prompt_tokens')} cached {v.get('notes_cached_tokens')}, "
              f"written {v.get('notes_written_tokens')}, chars per token {v['ratio']}")
except Exception as exc:
    print("   proxy: no status:", exc)
PY
}
start_pip_proxy() {  # tag, then ctxkeeper options
  local tag=$1; shift
  systemctl --user reset-failed ctx-keeper-proxy 2>/dev/null
  systemd-run --user --unit=ctx-keeper-proxy --collect "$VENV/bin/ctxkeeper" --port $PPORT --state-dir "$OUT/proxy-state/$tag" "$@" 2>&1 | tail -1
  up "http://127.0.0.1:$PPORT" || { say "proxy did not come up"; return 1; }
  journalctl --user -u ctx-keeper-proxy --no-pager -o cat 2>/dev/null | grep '^ctxkeeper' | tail -1 | sed 's/^/   /'
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
u = glob.glob(sys.argv[1] + "/*/usage.json") + glob.glob(sys.argv[1] + "/*/agent/usage.json")
if u:
    u = json.load(open(u[0]))
    print(f"   calls {u.get('n_lm_calls')}, prompt tokens {u.get('prompt_tokens')}, cached {u.get('cached_tokens')}, written {u.get('completion_tokens')}")
PYEOF
}

mkdir -p "$OUT/proxy-state" "$ODX/runs"
say "campaign 19 (ctxkeeper 1.0.0 release gate) start; MemAvailable $(avail) MiB"
[[ "$("$VENV/bin/ctxkeeper" --version)" == "ctxkeeper 1.0.0" ]] || { say "ABORT: $VENV has no ctxkeeper 1.0.0"; exit 2; }
"$VENV/bin/python" -c 'import openai' 2>/dev/null || { say "ABORT: no openai SDK in $VENV"; exit 2; }
docker image inspect $IMG >/dev/null 2>&1 || { say "ABORT: no image $IMG"; exit 2; }
[[ -e $ODX/tasks/$TASK/tests/spec.json ]] || { say "ABORT: no task $TASK"; exit 2; }
[[ -e $SRV ]] && { say "ABORT: $SRV already exists"; exit 2; }
for p in $PORT $PPORT $DPORT; do ss -tln | grep -q ":$p " && { say "ABORT: port $p is in use"; exit 2; }; done
[[ -n $(docker ps -q --filter name=fp8-tp) ]] && { say "ABORT: an fp8 container is already running"; exit 2; }
# the full-window server leaves ~2-3 GiB of host memory; a download beside it tripped the guard on the first try
[[ -n $(systemctl --user list-units --state=active --no-legend 'dl-*' 2>/dev/null) ]] && { say "ABORT: a download unit is running"; exit 2; }

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

# ---- the campaigns' research server (once)
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

if (( ready )); then
  # ---- G1: freeagent + the pip-installed proxy, --recipe qwen and nothing else
  job=$G1JOB
  if start_pip_proxy G1 --upstream "http://127.0.0.1:$PORT" --recipe qwen; then
    t0=$SECONDS
    say "[G1] freeagent on $TASK through ctxkeeper --recipe qwen; MemAvailable $(avail) MiB"
    timeout -s INT -k 180 3600 env API_BASE="http://127.0.0.1:$PPORT/v1" MODEL_NAME=qwen38-27b-fp8 TIME_LIMIT=3300 MAX_STEPS=900 \
        "$LAB/tools/freeagent/run-freeagent-job.sh" "$ODX/tasks/$TASK" "$ODX/runs" "$job" > "$OUT/G1.out" 2>&1
    say "[G1] done rc=$? in $(( (SECONDS-t0)/60 )) min $(( (SECONDS-t0)%60 )) s; MemAvailable $(avail) MiB"
    repair_result "$ODX/runs/jobs/$job"
    proxy_status "http://127.0.0.1:$PPORT" "$OUT/G1-proxy-status.json"
    systemctl --user stop ctx-keeper-proxy
    for c in $(docker ps -q --filter name=repair-); do docker rm -f "$c" >/dev/null 2>&1; done
    wait_idle || say "[G1] server still busy after 3 min"
  fi

  # ---- G2: long_chat.py through the Docker image, beyond the server's own window
  if [[ -z $(faults) ]] && server_up; then
    mkdir -p "$OUT/proxy-state/G2"
    docker rm -f ctxkeeper-g2 >/dev/null 2>&1
    docker run -d --name ctxkeeper-g2 --network host --user "$(id -u):$(id -g)" -v "$OUT/proxy-state/G2:/state" $IMG \
        --recipe qwen --upstream "http://127.0.0.1:$PORT" --port $DPORT >/dev/null
    if up "http://127.0.0.1:$DPORT"; then
      docker logs ctxkeeper-g2 2>&1 | head -1 | sed 's/^/   /'
      t0=$SECONDS
      say "[G2] long_chat.py, 300K tokens, through the Docker image"
      timeout 3600 python3 "$LAB/tools/ctxkeeper/examples/long_chat.py" --base-url "http://127.0.0.1:$DPORT/v1" --tokens 300000 \
          --extra-body '{"chat_template_kwargs": {"enable_thinking": false}}' > "$OUT/G2-long_chat.out" 2>&1
      say "[G2] done rc=$? in $(( (SECONDS-t0)/60 )) min $(( (SECONDS-t0)%60 )) s"
      tail -9 "$OUT/G2-long_chat.out" | sed 's/^/   /'
      proxy_status "http://127.0.0.1:$DPORT" "$OUT/G2-proxy-status.json"
    else
      say "[G2] the Docker proxy did not come up"; docker logs ctxkeeper-g2 2>&1 | tail -5
    fi
    docker rm -f ctxkeeper-g2 >/dev/null 2>&1
    wait_idle || say "[G2] server still busy after 3 min"
  fi

  # ---- G3: the README's OpenAI SDK snippet
  if [[ -z $(faults) ]] && server_up && start_pip_proxy G3 --upstream "http://127.0.0.1:$PORT" --recipe qwen; then
    say "[G3] OpenAI SDK: plain reply, tool call, streaming"
    timeout 600 "$VENV/bin/python" - > "$OUT/G3-sdk.out" 2>&1 <<'PY'
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:18200/v1", api_key="unused")
quick = {"chat_template_kwargs": {"enable_thinking": False}}
r = client.chat.completions.create(model="qwen38-27b-fp8", max_tokens=256, extra_body=quick,
                                   messages=[{"role": "user", "content": "Say hello in five words."}])
print("plain:", type(r).__name__, r.choices[0].finish_reason, repr(r.choices[0].message.content))
tools = [{"type": "function", "function": {"name": "shell", "description": "Run a bash command.",
          "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}]
r = client.chat.completions.create(model="qwen38-27b-fp8", max_tokens=512, extra_body=quick, tools=tools,
                                   messages=[{"role": "user", "content": "Use the shell tool to run `echo ok`."}])
calls = r.choices[0].message.tool_calls or []
print("tool call:", r.choices[0].finish_reason, [(c.function.name, c.function.arguments) for c in calls])
parts = [c.choices[0].delta.content or "" for c in client.chat.completions.create(
    model="qwen38-27b-fp8", max_tokens=256, extra_body=quick, stream=True,
    messages=[{"role": "user", "content": "Count from one to five in words."}]) if c.choices]
print("stream:", len(parts), "chunks", repr("".join(parts)))
PY
    say "[G3] done rc=$?"; sed 's/^/   /' "$OUT/G3-sdk.out" | cut -c1-240
    systemctl --user stop ctx-keeper-proxy
  fi
fi
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
if a: print(f"host memory available while the server ran: min {a[0]:.2f}  median {a[len(a)//2]:.2f} GiB  ({len(a)} samples)")
PY
for c in $(docker ps -q --filter name=repair-); do say "removing leftover task container $c"; docker rm -f "$c" >/dev/null 2>&1; done

# ---- Gemma back (G4 on its balanced recipe first), unless a fault was logged
F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
  exit 1
fi
if (( SKIP_G4 )); then
  say "kernel log clean since $START; G4 skipped (SKIP_G4=1); Gemma back on its throughput recipe"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
  F=$(faults); [[ -n $F ]] && { say "GPU FAULT LINES after the Gemma restart:"; echo "$F" | head -10 | cut -c1-220; }
  say "campaign $RUN complete"; exit 0
fi
say "kernel log clean since $START; Gemma on its balanced recipe for G4"
cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh balanced 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
if up "http://127.0.0.1:8000" && start_pip_proxy G4 --upstream http://127.0.0.1:8000 --recipe agent --budget 15360 --inplace-tokens 6000; then
  t0=$SECONDS
  say "[G4] long_chat.py, 100K tokens, through ctxkeeper --recipe agent to Gemma 4 26B on llama.cpp"
  timeout 3600 python3 "$LAB/tools/ctxkeeper/examples/long_chat.py" --base-url "http://127.0.0.1:$PPORT/v1" --tokens 100000 \
      > "$OUT/G4-long_chat.out" 2>&1
  say "[G4] done rc=$? in $(( (SECONDS-t0)/60 )) min $(( (SECONDS-t0)%60 )) s"
  tail -9 "$OUT/G4-long_chat.out" | sed 's/^/   /'
  proxy_status "http://127.0.0.1:$PPORT" "$OUT/G4-proxy-status.json"
  systemctl --user stop ctx-keeper-proxy
else
  say "[G4] Gemma or the proxy did not come up"
fi
say "Gemma back on its throughput recipe"
cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
F=$(faults)
[[ -n $F ]] && { say "GPU FAULT LINES after the Gemma restarts:"; echo "$F" | head -10 | cut -c1-220; }
say "campaign $RUN complete"
