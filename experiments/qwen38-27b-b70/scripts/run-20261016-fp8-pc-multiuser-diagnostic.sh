#!/usr/bin/env bash
# 2026-10-16 diagnostic (registered in notes/2026-10-04-fp8-multiuser-prereg.md before launch): the prefix-cache sweep's
# 2-user drafting arm had one long-prompt answer flip at a near tie (prose4k-c043, pass 2). Three fresh servers, two
# users each, on a near-tie detector suite (64 copies of prose4k that differ only in the runner's end marker), three
# passes, long suite only. Queue lines: "NAME KEY=VALUE ..." exported for that arm only. Gemma stopped first and put
# back on its throughput recipe at the end unless a GPU fault line was logged.
#   SUDO_ASKPASS=... systemd-run --user ... bash run-20261016-fp8-pc-multiuser-diagnostic.sh
set -uo pipefail
LAB=/home/steve/b70-optimization-lab
cd "$LAB"
export SUDO_ASKPASS=${SUDO_ASKPASS:?set SUDO_ASKPASS}
export MU_MODE=longsweep MU_PURE=1 MU_FA_PER_SEQ=1 MU_PREFILL_BATCH=8 MU_STATE_WIDTH=1 MU_SPEC_RESUME=1 MU_SEQS=2 \
  MU_IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r314-state-stride MU_SKIP_SHORT=1 MU_LONG_REPEATS=3 \
  MU_LONG_SUITE=$LAB/experiments/qwen38-27b-b70/data/2026-10-16-r314-sweep-pc/near-tie-prose4k-x8-suite.json
export B70_GUARD_MIN_AVAILABLE_GIB=1.6
ARMS=${ARMS:-"D1 MU_MTP=1 MU_PREFIX_CACHE=1;D2 MU_PREFIX_CACHE=1;D3 MU_MTP=1"}
TAG=${TAG:-20261016-pcdiag}
START=$(date '+%F %T')
FAULT_RE='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump has been created|Timedout job|timed out|wedged|device lost)|soft lockup'
say() { echo "### $(date +%H:%M:%S) $*"; }
faults() { sudo -A journalctl -k --since "$START" --no-pager -o short-iso 2>/dev/null | grep -Ei "$FAULT_RE"; }
restore() {
  F=$(faults)
  if [[ -n $F ]]; then say "GPU FAULT LINES since $START; cards left empty, Gemma NOT restored"; echo "$F" | head -10; return; fi
  say "kernel log clean since $START; Gemma back on its throughput recipe"
  timeout 900 scripts/gemma4-26b-two-b70-recipe.sh throughput 2>&1 | grep -E '^backend|^frontdoor|timed out|died'
  say "diagnostic $TAG complete"
}
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
IFS=';' read -ra arms <<< "$ARMS"
for spec in "${arms[@]}"; do
  read -r name kvs <<< "$spec"
  O=/mnt/fast-ai/bench-results/fp8-r314-$name-$TAG
  say "arm $name ($kvs) -> $O"
  env $kvs CAMPAIGN_OUT=$O python3 experiments/qwen38-27b-b70/scripts/run-20261004-fp8-multiuser-campaign.py || { say "arm failed rc=$?"; break; }
  [[ -f $O/FAULT-HALT.json ]] && { say "FAULT-HALT in $O"; break; }
  [[ -n $(faults) ]] && { say "kernel fault line; stopping"; break; }
done
