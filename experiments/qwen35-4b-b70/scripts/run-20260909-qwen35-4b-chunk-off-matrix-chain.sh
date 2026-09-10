#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 12 (2026-09-09): re-measure the lane with the FP16 linear chunk off.
#
# y1 (chain 11) showed the R224 32-row chunk is not a 21% tail-piece effect at c36 but a tax on every
# multi-piece step: the target lm_head is 248320 x 2560 fp16 = 1.2 GB and each piece re-reads it, so a
# depth-3 step at c64 (256 rows, eight pieces) streams ~10 GB through the vocabulary projection. With
# the chunk off, depth 3 gains 41% at c32 and 54% at c64. Every throughput figure in this lane above
# eight users at depth 3 - the speculation ceiling, the depth plateau, the TP2 matrix - was measured
# under that tax, and so was every no-speculation rung above c32. This chain re-measures them.
#
# z1/z3  TP1/TP2, engine defaults (mns 64, mbt 512, capture 64), c1..c64, both lanes.  The matrix rows.
# z5/z6  TP1/TP2 strict gates G1/G2/G3 at depth 3. Single user is one row and one piece either way, so
#        the headline should be byte-identical; this is the record that it is.
# z2/z4  TP1/TP2 with f4's settings (mns 128, mbt 1024, capture 128) at c64/c96/c128.
# z7/z8  TP1 depth 2 and depth 4, c1..c64: the depth plateau was measured under the tax too, and the
#        tax scales with rows per sequence, so it favoured shallower depths.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-chunkoff-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-chunkoff-20260909.pid"
log() { printf '[chunkoff %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

# Queue behind chain 11 and the 9B drift probe (its container is unnamed, so wait for its DONE file).
until [[ -e ${out}/drift-queued-20260909-DONE ]]; do sleep 30; done
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
hardware_abort() {
  [[ -f "$1/ABORTED" ]] || return 1
  grep -qiE 'not in normal state|fault signature|compute/XCCL health|container is still running|did not become healthy' "$1/ABORTED"
}
verify_chunk() {  # every server this arm launched must show the value
  local root=$1 want=$2 f n=0 ok=1
  for f in "${root}"/*/container-inspect.json; do
    [[ -e "$f" ]] || continue; n=$((n+1))
    grep -q "\"VLLM_XPU_FP16_LINEAR_ROWCHUNK=${want}\"" "$f" || { log "$(basename "${root}")/$(basename "$(dirname "$f")"): chunk=${want} NOT in container env"; ok=0; }
  done
  [[ ${n} -gt 0 ]] || { log "$(basename "${root}"): no container records"; ok=0; }
  [[ ${ok} == 1 ]] && log "$(basename "${root}"): chunk=${want} verified in ${n} container(s)"
  [[ ${ok} == 1 ]]
}
arm() {
  local label=$1; shift
  local root=${out}/qwen35-4b-w4a16-20260909-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 VLLM_XPU_FP16_LINEAR_ROWCHUNK=0 "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  verify_chunk "${root}" 0 || { echo "knob not applied in ${label}" >"${out}/qwen35-4b-chunkoff-20260909-STOPPED"; return 1; }
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-chunkoff-20260909-STOPPED"; return 1
  fi
  return 0
}

low="1,2,4,8,12,16,20,24,32,64"
hi_caps="1,2,4,8,16,20,24,32,40,48,56,64,80,96,112,128"
arm z1 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
arm z3 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
arm z5 TP=1 DEPTH=3 STAGES="strict" || exit 1
arm z6 TP=2 DEPTH=3 STAGES="strict" || exit 1
arm z2 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1
arm z4 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1
arm z7 TP=1 DEPTH=2 STAGES="ladders" LADDER_CONCURRENCY="1,4,8,16,32,64" LADDER_REPEATS=4 || exit 1
arm z8 TP=1 DEPTH=4 STAGES="ladders" LADDER_CONCURRENCY="1,4,8,16,32,64" LADDER_REPEATS=4 || exit 1

log "=== chain 12 complete ==="
echo done >"${out}/qwen35-4b-chunkoff-20260909-DONE"
