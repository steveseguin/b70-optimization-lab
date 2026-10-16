#!/usr/bin/env bash
# Campaign 24b (2026-10-16, registered in the lab note before any run): which setting of the context server breaks
# drafting (MTP5) with two requests. Campaign 24's server (all four multi-user fixes plus prefix caching in align mode,
# 262K, 832-token steps) gave 2 garbage and 27 of 36 overlapped replies different from solo; the 2026-10-15
# multi-user server (no prefix caching, 33K, 4,096-token steps, prompt batching 8) was exact. One fresh server per
# queue line, each running scripts/context/concurrency_check.py (3 rounds, against campaign 23b's MTP0 solo replies).
# Queue lines: "NAME key=value ...", keys pc (1 = prefix caching align + exact overlay), len, batched, xpb (prompt
# batching of the pure-step overlay; 0 = its default), mtp, seqs. Gemma is stopped once and restored at the end.
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
CTX=$LAB/experiments/qwen38-27b-b70/scripts/context
O=/mnt/fast-ai/bench-results/context-longrun-20261016
Q=${QUEUE:-$O/QUEUE24b.txt}
PORT=18196
REF=$LAB/experiments/qwen38-27b-b70/data/2026-10-16-context-campaign23/logs/c23b-X-check-s0.json
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
avail() { awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
server_up() { curl -fsS -m 10 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; }

say "campaign 24b start; queue $Q; MemAvailable $(avail) MiB"
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

n=0
while :; do
  [[ -e $O/STOP-CAMPAIGN24B ]] && { say "stopped by STOP-CAMPAIGN24B"; break; }
  [[ -n $(faults) ]] && { say "GPU fault line in the kernel log; no further servers"; break; }
  line=$(grep -vE '^\s*(#|$)' "$Q" | sed -n "$((n+1))p")
  [[ -z $line ]] && { say "queue done after $n lines"; break; }
  n=$((n+1))
  read -r name rest <<< "$line"
  pc=1 len=262144 batched=832 xpb=0 mtp=5 seqs=2
  for kv in $rest; do case ${kv%%=*} in pc|len|batched|xpb|mtp|seqs) printf -v "${kv%%=*}" '%s' "${kv#*=}" ;; *) say "unknown key in '$line'";; esac; done
  SRV=$O/server/c24b-$name
  pcflags=() xpflags=()
  (( pc )) && pcflags=(--prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 --serve-arg=--prefix-cache-retention-interval=13312)
  (( xpb )) && xpflags=(--extra-env B70_EXCLUSIVE_PREFILL_BATCH=$xpb)
  for i in $(seq 1 30); do [[ -z $(ss -Htan "( sport = :$PORT or dport = :$PORT )") ]] && break; sleep 5; done
  say "[$name] pc=$pc len=$len batched=$batched xpb=$xpb mtp=$mtp seqs=$seqs: starting the server; MemAvailable $(avail) MiB"
  systemctl --user reset-failed ctx-fp8-tp2-server 2>/dev/null
  systemd-run --user --unit=ctx-fp8-tp2-server --collect -p WorkingDirectory=$LAB -E B70_GUARD_MIN_AVAILABLE_GIB=1.6 \
    python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py --out "$SRV" --port $PORT \
    --image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800 \
    --tp 2 --mem 0.95 --max-model-len "$len" --batched "$batched" --seqs "$seqs" --fa-verify-rows --mtp "$mtp" \
    $( (( mtp )) && echo --draft-int4 --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt) \
    --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1 \
    --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1 \
    --serve-arg=--enable-auto-tool-choice --serve-arg=--tool-call-parser=qwen3_coder --serve-arg=--reasoning-parser=qwen3 \
    "${pcflags[@]}" \
    --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
    --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1 \
    --overlay b70-exclusive-prefill --extra-env B70_EXCLUSIVE_PREFILL=1 "${xpflags[@]}" \
    --overlay b70-fa-decode-per-seq --extra-env B70_FA_DECODE_PER_SEQ=1 2>&1 | tail -1
  ready=0
  for i in $(seq 1 120); do
    if server_up; then ready=1; say "[$name] server ready after ~$((i*15)) s; MemAvailable $(avail) MiB"; break; fi
    systemctl --user is-active --quiet ctx-fp8-tp2-server || { say "[$name] server unit ended before ready"; break; }
    [[ -n $(faults) ]] && { say "[$name] GPU fault line during server start"; break; }
    sleep 15
  done
  if (( ready )); then
    (cd "$CTX" && timeout -s INT -k 60 900 python3 ./concurrency_check.py --base-url "http://127.0.0.1:$PORT/v1" --rounds 3 \
      --reference "$REF" --json "$O/c24b-$name.json" > "$O/c24b-$name.out" 2>&1)
    rc=$?
    say "[$name] check rc=$rc (0 all same, 1 some different, 2 garbage): $(tail -1 "$O/c24b-$name.out")"
  fi
  if systemctl --user is-active --quiet ctx-fp8-tp2-server; then
    touch "$SRV/STOP"
    for i in $(seq 1 40); do systemctl --user is-active --quiet ctx-fp8-tp2-server || break; sleep 5; done
    systemctl --user is-active --quiet ctx-fp8-tp2-server && systemctl --user stop ctx-fp8-tp2-server
  fi
  [[ -e $SRV/MEMORY-GUARD.json ]] && say "[$name] MEMORY GUARD fired"
  sleep 5
done

F=$(faults)
if [[ -n $F ]]; then
  say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored:"; echo "$F" | head -10 | cut -c1-220
else
  say "kernel log clean since $START; restoring Gemma (throughput)"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
fi
say "campaign 24b complete"
