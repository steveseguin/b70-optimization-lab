#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 3 (2026-09-09): speculation depth as a dose, and TP2 statistics.
#
# f1 established that depth 3 raises the c64 divergence rate from 0.70% to 13.28%, and f2 showed the
# XPU decode graph capture is not responsible (c64 identically 1110/1280 with capture on and off,
# knob verified in the container env and the server's cudagraph_mode). The remaining suspect is the
# speculative verify step itself. If it is, the rate should scale with the number of speculative
# tokens per step, because that is what changes the verify batch's row count and its composition.
#
# So: measure the c64 rate at depth 1, 2 and 6 against f1's depth 3. A monotone dose-response over
# four depths is much stronger evidence than any single-arm comparison, and it costs four ladders.
# Depth 4 and 5 were already shown lossless on the strict suite (2026-09-08 depth sweep) but were
# never run as identity ladders, so the ladder rate at depth is genuinely unmeasured everywhere.
#
# Each arm also runs its own MTP0 ladder, so the chain accumulates roughly 5000 additional MTP0 c64
# requests. The one clean stutter insertion on record (benchmark-c043, " inference" duplicated) came
# from a TP2 MTP0 c64 pass of 128 requests; it has not recurred in f1's 1920. t5 puts 1280 TP2 MTP0
# c64 requests against it on the configuration where it appeared.
#
# Waits for chain 5, which waits for chain 2, which waits for chain 1. One lane per host.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-depth-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-depth-20260909.pid"
log() { printf '[dose %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

log "waiting for chain 7 (stagger replication)"
while [[ ! -e "${out}/qwen35-4b-stagger-20260909-DONE" && ! -e "${out}/qwen35-4b-stagger-20260909-STOPPED" ]]; do sleep 60; done
[[ -e "${out}/qwen35-4b-stagger-20260909-STOPPED" ]] && { log "chain 7 stopped; not starting"; exit 1; }
log "chain 7 done"

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
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-depth-20260909-STOPPED"; return 1
  fi
  return 0
}

# Dose-response in speculation depth at a fixed rung. f1 supplies depth 3.
arm e1 TP=1 DEPTH=1 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1
arm e2 TP=1 DEPTH=2 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1
arm e6 TP=1 DEPTH=6 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1

# TP2 statistics at the rung, on the configuration where the one stutter insertion appeared.
arm t5 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1

# TP2 against the fragile suite, for a matched high-rate comparison with chain 2's g1.
arm t6 TP=2 DEPTH=3 STAGES="ladders" LADDER_SUITE="${fragile}" \
    LADDER_EXTRA_ARGS="--verbatim-prompts" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 || exit 1

log "=== chain 3 complete ==="
echo done >"${out}/qwen35-4b-depth-20260909-DONE"
