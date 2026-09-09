#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 6 (2026-09-09): strict-suite gates at depth 1 and depth 2.
#
# The 2026-09-08 depth sweep covered depths 3, 4, 5 and 6 on the strict suite and found all four
# lossless, with 3 and 4 tied at the top. Depths 1 and 2 were never run there, so the lane can say
# "depth 3 is the lossless pick among 3-6" but has no gate result for the two shallower settings.
# Chain 3's e1 and e2 arms give them identity ladders at c64; this gives them the strict pair, which
# is what "lossless at depth n" means in this lab's terms: G1 MTP0 a/b exact, G2 depth-n a/b exact,
# G3 depth-n against the MTP0 oracle exact, plus a class-balanced rate to compare against depth 3's
# 177.4 tok/s.
#
# Cheap and complete rather than novel: four servers per arm, and it closes the depth axis the user
# asked for (MTP 0, 1, 2, 3) with the same evidence at every rung.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-shallow-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-shallow-20260909.pid"
log() { printf '[shallow %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

log "waiting for chain 4 (margin probe)"
while [[ ! -e "${out}/qwen35-4b-margin-20260909-DONE" ]]; do
  [[ -e "${out}/qwen35-4b-gdn-20260909-STOPPED" || -e "${out}/qwen35-4b-depth-20260909-STOPPED" ]] && { log "an upstream chain stopped; not starting"; exit 1; }
  sleep 60
done
log "chain 4 done"

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
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 STAGES="strict" "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-shallow-20260909-STOPPED"; return 1
  fi
  # A G1 failure aborts the arm and is a result, not a fault; the chain continues.
  return 0
}

arm d1s DEPTH=1 || exit 1
arm d2s DEPTH=2 || exit 1

# mb: isolate why f4's depth-3 c64 rate (20/384, 5.21%) is far below f1's (170/1280, 13.28%);
# Poisson P(<=20 | 51.0) = 6.7e-07, so the difference is real. The two arms differ in three settings
# at once - capture ceiling 64 vs 128, max_num_seqs 64 vs 128, max_num_batched_tokens 512 vs 1024 -
# and at c64 depth 3 the decode step is 256 tokens, past both ceilings, so capture is inactive in
# both. That points at the scheduler settings rather than capture, and on a GDN hybrid the prefill
# chunking is a live suspect: all 64 prompts arrive together and the chunk boundaries set how the
# recurrent state is accumulated. This arm holds the capture ceiling at f1's 64 and takes f4's
# max_num_seqs and max_num_batched_tokens, completing the 2x2:
#
#   f1  capture 64,  mns 64,  mbt 512   -> 13.28%
#   mb  capture 64,  mns 128, mbt 1024  -> ?
#   f4  capture 128, mns 128, mbt 1024  -> 5.21%
#
# mb near 5% blames the scheduler settings; near 13% blames the capture configuration.
arm mb DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 \
    LADDER_MNS=128 LADDER_MBT=1024 || exit 1

log "=== chain 6 complete ==="
echo done >"${out}/qwen35-4b-shallow-20260909-DONE"
