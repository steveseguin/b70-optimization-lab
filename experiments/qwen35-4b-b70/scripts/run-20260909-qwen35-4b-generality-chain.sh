#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 10 (2026-09-09): the three questions the campaign left open.
#
# x1  Does the stagger recipe hold at rungs other than c64? Every exactness arm so far is at c64, and
#     that is the one thing wrong with recommending it: a deployment sized for 32 or 128 users is
#     outside everything measured. Runs TP2 with a 5 ms stagger at c16, c32, c96 and c128. If any rung
#     is not exact, the recommendation needs a concurrency range attached to it.
#
# x2  What is the c40 throughput dip? One card reads 1595 tok/s at c32, 1360 at c40 and 1732 at c64
#     without speculation, reproduced to 0.1% across two arms, and nothing explains it. This maps it
#     at 32/36/40/44/48/56/64 with every rung present in the capture set, so graph padding cannot be
#     the cause - at MTP0 an uncaptured c36 would pad to 40 and c44 to 50, which is itself a candidate
#     and is removed here by construction.
#
# x3  Do the two levers compose? max_num_batched_tokens 1024 halves depth-3 divergence by reshaping
#     the composition history; the stagger makes that history reproducible. They are different
#     mechanisms, so their combination is not predictable from either alone. Depth 3 is where it
#     matters, since that is the lane the stagger does not make exact.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-gen-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-gen-20260909.pid"
log() { printf '[gen %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

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
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 DEPTH=3 STAGES="ladders" "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-gen-20260909-STOPPED"; return 1
  fi
  return 0
}

# x1: is the stagger exact away from c64? Capture sizes and ceiling raised together so c128 is a
# captured MTP0 shape; max_num_seqs 128 so the top rung can actually fill.
arm x1 TP=2 LADDER_CONCURRENCY="16,32,96,128" LADDER_REPEATS=10 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="1,2,4,8,16,20,24,32,40,48,56,64,80,96,112,128" CAPTURE_MAX=128 \
    LADDER_EXTRA_ARGS="--launch-stagger-ms 5" || exit 1

# x2: map the throughput dip with every rung captured, so padding is not the explanation.
arm x2 TP=1 LADDER_CONCURRENCY="32,36,40,44,48,56,64" LADDER_REPEATS=10 \
    CAPTURE_SIZES="1,2,4,8,16,24,32,36,40,44,48,52,56,60,64" CAPTURE_MAX=64 || exit 1

# x3: do the levers compose? Depth 3, fragile suite, both applied.
arm x3 TP=1 LADDER_CONCURRENCY="64" LADDER_REPEATS=20 LADDER_MNS=128 LADDER_MBT=1024 \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" || exit 1

log "=== chain 10 complete ==="
echo done >"${out}/qwen35-4b-gen-20260909-DONE"
