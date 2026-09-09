#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 7 (2026-09-09): replicate and bound the staggered-admission exactness result.
#
# g3's MTP0 arm returned 1280/1280 byte-identical to the sequential oracle at c64 with 25 ms of
# per-index arrival stagger, against 35/1280 and 24/1280 divergent in its two matched barrier arms.
# Poisson P(0 | 30) = 1.5e-13, and the harness certified it output-identity-qualified on its own.
#
# It is also one arm, on one rung, on one card, at one stagger value, on a suite deliberately selected
# for divergence. Every other single-arm result tonight that looked clean has been worth re-checking,
# and two of them changed on the re-check. This runs the checks before the claim travels.
#
#   r1  exact replicate of g3's configuration. Does 0/1280 reproduce?
#   r2  the same stagger on the FULL 2026-08-25 suite rather than the fragile one. The fragile suite is
#       a biased instrument; if exactness is real it should hold on the unbiased suite too, where the
#       barrier baseline is 0.70% rather than 2.73%.
#   r3  5 ms instead of 25 ms. The cohort ramp is then 315 ms rather than 1.575 s, and the throughput
#       cost should fall with it. If 5 ms is also exact, the lever is much cheaper than 14.2%.
#
# Each arm's speculative ladder runs too and is kept: depth 3 under stagger was 44.61% divergent with
# 95.45% slot reproducibility, and more samples of that are useful even though the headline is MTP0.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-stagger-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-stagger-20260909.pid"
log() { printf '[stag %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

log "waiting for chain 5"
while [[ ! -e "${out}/qwen35-4b-gdn-20260909-DONE" && ! -e "${out}/qwen35-4b-gdn-20260909-STOPPED" ]]; do sleep 60; done
[[ -e "${out}/qwen35-4b-gdn-20260909-STOPPED" ]] && { log "chain 5 stopped; not starting"; exit 1; }
log "chain 5 done"

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
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="ladders" \
      LADDER_CONCURRENCY="64" LADDER_REPEATS=20 "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-stagger-20260909-STOPPED"; return 1
  fi
  return 0
}

arm r1 LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 25" || exit 1
arm r2 LADDER_EXTRA_ARGS="--launch-stagger-ms 25" || exit 1
arm r3 LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" || exit 1

log "=== chain 7 complete ==="
echo done >"${out}/qwen35-4b-stagger-20260909-DONE"
