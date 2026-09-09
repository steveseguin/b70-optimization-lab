#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 9 (2026-09-09): does staggered admission give exactness on two cards too?
#
# The staggered-admission result is TP1-only: four arms, all at c64 on one card, all exact at MTP0.
# Two cards are the better configuration on both axes at that rung - 0.16% divergent against 0.70%
# and 2786 tok/s against 1723 - so the recipe a reader would actually deploy is TP2, and whether the
# stagger closes the remaining 0.16% there is the question that matters for it.
#
#   w1  TP2, 5 ms stagger, full suite. The direct test, at the stagger value that costs 1% on one card.
#   w2  TP2, 5 ms stagger, fragile suite. The harder version: TP2's fragile-suite MTP0 rate is 1.33%,
#       eight times its full-suite rate, so this is where an incomplete fix would show.
#
# Both arms also run their speculative ladder, which gives the first TP2 slot-consistency data - on one
# card the stagger takes modal minority-slot recurrence from 33.8% to 95.45%, and whether that holds
# across topology is unmeasured.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-tp2stag-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-tp2stag-20260909.pid"
log() { printf '[tp2s %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

log "waiting for chain 8"
while [[ ! -e "${out}/qwen35-4b-mbase-20260909-DONE" && ! -e "${out}/qwen35-4b-mbase-20260909-STOPPED" ]]; do sleep 60; done
[[ -e "${out}/qwen35-4b-mbase-20260909-STOPPED" ]] && { log "chain 8 stopped; not starting"; exit 1; }
log "chain 8 done"

wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
hardware_abort() {
  [[ -f "$1/ABORTED" ]] || return 1
  grep -qiE 'not in normal state|fault signature|compute/XCCL health|container is still running|did not become healthy' "$1/ABORTED"
}
arm() {
  local label=$1; shift
  local root=${out}/qwen35-4b-w4a16-20260909-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=2 DEPTH=3 STAGES="ladders" \
      LADDER_CONCURRENCY="64" LADDER_REPEATS=20 "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-tp2stag-20260909-STOPPED"; return 1
  fi
  return 0
}

arm w1 LADDER_EXTRA_ARGS="--launch-stagger-ms 5" || exit 1
arm w2 LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" || exit 1

log "=== chain 9 complete ==="
echo done >"${out}/qwen35-4b-tp2stag-20260909-DONE"
