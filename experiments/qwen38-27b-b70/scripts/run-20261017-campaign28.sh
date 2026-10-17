#!/usr/bin/env bash
# Campaign 28 (2026-10-17; registered in notes/2026-10-17-fp8-agent-draft-depth.md before any run): one-launch census
# at 7 and 8 rows on card 0, then campaign 27's server at depth 6 (c28a) and, if every c28a call equals c27a's, at
# depth 7 (c28b); each on K32 and K64. Gemma is stopped once and restored once at the end, unless a GPU fault line.
#   SUDO_ASKPASS=... systemd-run --user --unit=ctx-campaign28 ... bash run-20261017-campaign28.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
E=$LAB/experiments/qwen38-27b-b70
S=$E/scripts
D=$E/data/2026-10-17-context-campaign28
O=/mnt/fast-ai/bench-results/context-longrun-20261016
CD=/mnt/fast-ai/bench-results/fp8-agent-depth-census-20261017
IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
restore() {
  docker rm -f verify-census >/dev/null 2>&1
  F=$(faults)
  if [[ -n $F ]]; then say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored"; echo "$F" | head -10; return; fi
  say "kernel log clean since $START; Gemma back on its throughput recipe"
  cd "$LAB" && timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
  say "campaign 28 complete"
}
same_calls() {  # run -> 0 when both arms' calls equal c27a's
  local rc=0 arm a b
  for arm in K32 K64; do
    a=$(ls $O/proxy-state/c27a-$arm-rules-s0/*/calls.jsonl 2>/dev/null | head -1)
    b=$(ls $O/proxy-state/$1-$arm-rules-s0/*/calls.jsonl 2>/dev/null | head -1)
    [[ -n $a && -n $b ]] || { say "$1 $arm: call log missing"; rc=1; continue; }
    python3 $S/compare-campaign-calls.py "$a" "$b" | sed "s/^/   $1 $arm: /" || rc=1
  done
  return $rc
}
mkdir -p "$D" "$CD"
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
trap restore EXIT
for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 2; done
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server still running"; exit 2; }
sleep 5

for q in 7 8; do
  say "census, $q rows, pages of 832"
  docker run --rm --name verify-census --device /dev/dri:/dev/dri --group-add render --memory 6g --ulimit core=0 \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -v "$S/census-verify-rows.py:/tmp/b.py:ro" -v "$CD:/out" \
    -v "$E/overlays/b70-fa-verify-rows/b70_fa_verify_rows.py:/tmp/ov.py:ro" --workdir /tmp --entrypoint python3 "$IMAGE" \
    /tmp/b.py --qlen $q --pages 832 --overlay /tmp/ov.py --out "/out/census-q$q.json" 2>&1 | grep -E '^\{|mismatches' | cut -c1-300
  cp "$CD/census-q$q.json" "$D/" 2>/dev/null
  python3 - "$D/census-q$q.json" <<'PY' || { say "census at $q rows failed: no server runs"; exit 1; }
import json, sys
p = json.load(open(sys.argv[1]))["pages"]
ok = all(x["summary"]["pinned_used"] > 0 and x["summary"]["pinned_all_equal"] == x["summary"]["pinned_used"] for x in p)
print("   census", sys.argv[1].rsplit("/", 1)[1], "one launch = lone rows at every used length:", ok)
sys.exit(0 if ok else 1)
PY
done
[[ -n $(faults) ]] && { say "GPU fault line after the census; no servers"; exit 1; }

RUN=c28a MTP=6 SEQS=1 ONE_LAUNCH=1 TAIL=1 EDIT=0 RESTORE=0 IDLE_MAX=5 bash $S/longrun-campaign28.sh > "$D/c28a.log" 2>&1
grep "^###\|RESULT" "$D/c28a.log" | tail -6
if ! same_calls c28a; then say "c28a differs from c27a: depth 7 not run"; exit 1; fi
[[ -n $(faults) ]] && { say "GPU fault line after c28a; depth 7 not run"; exit 1; }
RUN=c28b MTP=7 SEQS=1 ONE_LAUNCH=1 TAIL=1 EDIT=0 RESTORE=0 IDLE_MAX=5 bash $S/longrun-campaign28.sh > "$D/c28b.log" 2>&1
grep "^###\|RESULT" "$D/c28b.log" | tail -6
same_calls c28b || say "c28b differs from c27a"
