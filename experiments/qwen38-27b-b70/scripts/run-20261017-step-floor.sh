#!/usr/bin/env bash
# 2026-10-17 the writing-step floor: why a context-lane step costs 38.5 ms at 1K when the TP2 package's is quoted at
# 33.0 (registered in notes/2026-10-17-fp8-step-floor.md before any run). Six R314 servers in turn, the same write
# probe on each (probe-write-rate-vs-context.py: copy and story, 512 tokens, at 1K / 8K / 16K / 30K):
#   L  the context lane as campaign 27 ran it (pieces of 832, exact cache with the tail switch, one launch)
#   N  L without the prefix cache and the overlays that serve it (same 262,144 window, same 832-token steps)
#   M  the package's flags with L's window (262,144, steps of 4,096, no prefix cache)
#   P  the package's flags (33,024 window, steps of 4,096, no prefix cache), on R314
#   P0, L0  P and L without the drafter (one token per step: the step without speculation, measured the same way)
# All: TP2, MTP5 with INT4 draft head + shortlist (except P0, L0), allgather, chunked-upload and GDN state-width overlays, verify rows
# in one launch, and the host step clock (b70-host-step-clock: time only, one line per answer per card). No profiler: a guard kill mid-step resets an engine (06:00 fault), and a profile needs host memory.
# Stops at the first fault line or failed start; the cards are left empty (RESTORE=1 puts Gemma back at the end).
#   SUDO_ASKPASS=... [ALLOW_GEMMA_STOP=1] [ARMS="L N M P P0 L0"] systemd-run --user ... bash run-20261017-step-floor.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
export B70_GUARD_MIN_AVAILABLE_GIB=1.6
TAG=${TAG:-20261017-floor}
O=
D=$LAB/experiments/qwen38-27b-b70/data/2026-10-17-step-floor
S=$LAB/experiments/qwen38-27b-b70/scripts
PORT=18196
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
stop_server() {
  [[ -d $O ]] || return
  touch "$O/STOP"
  for i in $(seq 1 90); do [[ -n ${OWNER:-} ]] && kill -0 "$OWNER" 2>/dev/null || break; sleep 2; done
  say "server stopped: $(python3 -c "import json;s=json.load(open('$O/state.json'));print(s.get('status'), s.get('stop_confirmed'))" 2>/dev/null)"
  O=
}
finish() {
  stop_server
  F=$(faults)
  if [[ -n $F ]]; then say "GPU FAULT LINES since $START; cards left empty"; echo "$F" | head -10; return; fi
  if [[ ${RESTORE:-0} == 1 ]]; then
    say "kernel log clean since $START; Gemma back on its throughput recipe"
    timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
  else
    say "kernel log clean since $START; cards left empty"
  fi
  say "campaign $TAG complete"
}
wait_port() {  # a stop leaves the port in TIME_WAIT; the launcher's bind probe fails with Errno 98 until it clears
  for i in $(seq 1 120); do ss -tanH "( sport = :$PORT or dport = :$PORT )" | grep -q . || return 0; sleep 2; done
  say "port $PORT still busy"; return 1
}
COMMON=(--image neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride --warmup --keep --startup-timeout 1800
        --tp 2 --mem 0.95 --seqs 1 --fa-verify-rows
        --overlay b70-allgather-allreduce --extra-env B70_ALLGATHER_ALLREDUCE=1
        --overlay b70-chunked-upload --extra-env B70_CHUNKED_UPLOAD=1
        --overlay b70-gdn-state-width --extra-env B70_GDN_STATE_WIDTH=1
        --overlay b70-host-step-clock --extra-env B70_HOST_STEP_CLOCK=1
        --extra-env B70_FA_VERIFY_ROWS_ONE_LAUNCH=1)
arm_args() {  # an arm name ending in 0 is the same server without the drafter
  if [[ $1 == *0 ]]; then echo --mtp 0
  else echo --mtp 5 --draft-int4 --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt
  fi
  case ${1%0} in
    L) echo --max-model-len 262144 --batched 832 \
         --prefix-cache align --overlay b70-prefix-cache-exact --extra-env B70_PREFIX_CACHE_EXACT=1 \
         --extra-env B70_PREFIX_CACHE_EXACT_TAIL=1 --serve-arg=--prefix-cache-retention-interval=13312 \
         --overlay b70-spec-resume-accepted --extra-env B70_SPEC_RESUME_ACCEPTED=1 \
         --overlay b70-exclusive-prefill --extra-env B70_EXCLUSIVE_PREFILL=1 ;;
    N) echo --max-model-len 262144 --batched 832 \
         --overlay b70-exclusive-prefill --extra-env B70_EXCLUSIVE_PREFILL=1 ;;
    M) echo --max-model-len 262144 --batched 4096 ;;
    P) echo --max-model-len 33024 --batched 4096 ;;
    *) return 1 ;;
  esac
}
start_server() {  # arm
  local name=$1 extra
  extra=$(arm_args "$name") || { say "unknown arm $name"; return 1; }
  wait_port || return 1
  [[ -n $(faults) ]] && { say "ABORT: GPU fault line before $name"; return 1; }
  O=/mnt/fast-ai/bench-results/fp8-r314-floor-$name-$TAG
  [[ -e $O ]] && { say "ABORT: $O exists"; return 1; }
  # shellcheck disable=SC2086
  python3 $S/run-fp8-tp1-server.py --out "$O" --port $PORT "${COMMON[@]}" $extra > "$D/owner-$name.log" 2>&1 &
  OWNER=$!
  local s=
  for i in $(seq 1 400); do
    s=$(python3 -c "import json;print(json.load(open('$O/state.json')).get('status'))" 2>/dev/null)
    [[ $s == ready ]] && break
    [[ $s == failed || $s == stopped* ]] && { say "server $name $s"; return 1; }
    kill -0 $OWNER 2>/dev/null || { say "owner $name exited before ready"; return 1; }
    [[ -n $(faults) ]] && { say "GPU fault line during $name start"; return 1; }
    sleep 5
  done
  [[ $s == ready ]] || { say "server $name not ready in time"; return 1; }
  say "server $name ready: $extra"
  grep -o "Setting attention block size to [0-9]* tokens\|b70_fa_verify_rows: enabled.*\|b70_prefix_cache_exact[^:]*: [a-z][^(]*" \
    "$O/server.log" | sort -u
}

[[ $(cat /proc/sys/kernel/random/boot_id) == 66541315-49f1-41f7-af1d-4756d6b89c9c ]] && { say "still the faulted boot; nothing run"; exit 1; }
for u in ctx-campaign28f ctx-fp8-tp2-server; do
  systemctl --user is-active --quiet $u && { say "unit $u is still running; nothing run"; exit 1; }
done
[[ -n $(docker ps -q) ]] && { say "containers running; nothing run"; docker ps --format '{{.Names}} {{.Image}}'; exit 1; }
if systemctl is-active --quiet gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service; then
  [[ ${ALLOW_GEMMA_STOP:-0} == 1 ]] || { say "Gemma LAN service is up; ALLOW_GEMMA_STOP=1 to stop it first"; exit 1; }
  say "stopping the Gemma service"
  sudo -A systemctl stop gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service
fi
for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 2; done
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server still running"; exit 2; }
mkdir -p "$D"
trap finish EXIT
for arm in ${ARMS:-L N M P P0 L0}; do
  OWNER=; start_server "$arm" || exit 1
  python3 $S/probe-write-rate-vs-context.py --base-url http://127.0.0.1:$PORT --lengths 1000,8000,16000,30000 \
    --out "$D/write-$arm.json" > "$D/write-$arm.log" 2>&1 || say "write probe failed on $arm"
  grep "^WRITE" "$D/write-$arm.log"
  grep -o "b70_host_step_clock rank .*" "$O/server.log" > "$D/clock-$arm.txt"; head -c 600 "$D/clock-$arm.txt"; echo
  stop_server
  [[ -n $(faults) ]] && { say "ABORT: GPU fault line after $arm"; exit 1; }
done
