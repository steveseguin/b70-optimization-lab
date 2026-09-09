#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 2 (2026-09-09): powered mechanism arms, designed from chain 1's f1 results.
#
# f1 gave the rates that make these worth running. Per request at c64 on one card: MTP0 0.70%
# (9/1280), MTP3 13.28% (170/1280). The speculative arm at c64 therefore produces ~8.5 events per
# pass on the full suite, and the fragile suite built from f1 (16 prompts, mean per-pass rate 52%)
# should produce several times that. That is enough to compare interventions by rate rather than by
# whether a pass came back clean.
#
# Arms:
#   d1  determinism pad ON at depth 3. The pad is inert below 128 decode rows, so it does nothing at
#       MTP0 c64 (64 rows) but is active at depth 3 c64 (256 rows). f1's MTP3 c64 is the matched
#       control at 170/1280. It was measured on the 9B as -13% throughput with no identity gain; on
#       the 4B nobody has looked, and the new classification says it targets the substitution half,
#       which is 84% of 4B divergences - so here it has a mechanism to act on.
#   g1  fragile suite, full capture. Establishes the fragile-suite baseline rate for both arms.
#   g2  fragile suite with --pin-slots. Pins expanded prompt i to slot concurrency-1-i. If divergence
#       is a function of slot position, pinning makes it repeatable; if it is not, the rate is
#       unchanged. This is a direct test of the row-position story behind the whole pad/row-invariance
#       line of work.
#   g3  fragile suite with --launch-stagger-ms 25. Spreads arrivals so fewer copies land in the same
#       decode step. If co-residency in a step is what perturbs a site, the rate should fall.
#
# Waits for chain 1 to finish before touching the cards: one lane per host, and two servers on the
# same two cards both fail health (R265/R267a).
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-fragile-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-fragile-20260909.pid"

log() { printf '[frag %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

log "waiting for chain 1 to finish"
while [[ ! -e "${out}/qwen35-4b-exhaustive-20260909-DONE" && ! -e "${out}/qwen35-4b-exhaustive-20260909-STOPPED" ]]; do sleep 60; done
if [[ -e "${out}/qwen35-4b-exhaustive-20260909-STOPPED" ]]; then
  log "chain 1 stopped on a hardware abort; not starting chain 2"; exit 1
fi
log "chain 1 done"

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
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-fragile-20260909-STOPPED"; return 1
  fi
  return 0
}

# d1: determinism pad on, depth 3, matched to f1's MTP3 c64 control.
arm d1 TP=1 DEPTH=3 GRAPH=1 W4A16_PAD=1 STAGES="ladders" \
    LADDER_CONCURRENCY="32,64" LADDER_REPEATS=20 || exit 1

# g1/g2/g3: fragile suite. verbatim keeps the copies byte-identical so the site survives expansion.
arm g1 TP=1 DEPTH=3 GRAPH=1 W4A16_PAD=0 STAGES="ladders" \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts" \
    LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1

arm g2 TP=1 DEPTH=3 GRAPH=1 W4A16_PAD=0 STAGES="ladders" \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --pin-slots" \
    LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1

arm g3 TP=1 DEPTH=3 GRAPH=1 W4A16_PAD=0 STAGES="ladders" \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 25" \
    LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1

log "=== chain 2 complete ==="
echo done >"${out}/qwen35-4b-fragile-20260909-DONE"
