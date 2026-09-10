#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 11 (2026-09-09): is the throughput dip the 32-row FP16 linear chunk?
#
# x2 mapped the no-speculation dip with every rung graph-captured: 1593 tok/s at c32, 1253 at c36, then
# 1360, 1438, 1508, 1623, 1727 at c40/44/48/56/64. Padding is eliminated by construction. The shape is
# a cliff at 32->36 followed by a linear recovery to 64, and one thing in the server has exactly that
# shape: the R224 overlay runs every unquantized FP16 linear (lm_head, mtp.fc) in pieces of at most 32
# rows, so above 32 sequences the last piece holds 4, 8, 12, 16, 24 and then 32 rows - and throughput
# rises monotonically with that tail. The depth-3 lane, at four rows per sequence, dips only at c36
# and c44, the two rungs whose row count leaves a 16-row tail. Three arms:
#
# y1  Same rungs and capture set as x2 with the chunk disabled (VLLM_XPU_FP16_LINEAR_ROWCHUNK=0). If
#     the dip is the chunk, c36 reads at or above c32 and the recovery ramp is gone. Both lanes read
#     identity too, since the chunk was introduced as a batch-invariance lever.
# y2  A prospective prediction with the chunk left at 32: past c64 the next cliff is at c68 (tail 4)
#     and it should be gone again by c96 (three full pieces). Rungs 64/68/72/80/96 with all captured.
# y3  The deployable recipe under the fix: MTP0, fragile suite, 5 ms stagger, chunk 0. g3/r1/r3 gave
#     1280/1280 with the chunk at 32; the ordering argument says it should not matter, but a
#     recommendation that changes two things at once needs the pair measured together.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-rowchunk-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-rowchunk-20260909.pid"
log() { printf '[rowchunk %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
hardware_abort() {
  [[ -f "$1/ABORTED" ]] || return 1
  grep -qiE 'not in normal state|fault signature|compute/XCCL health|container is still running|did not become healthy' "$1/ABORTED"
}
# Fail closed if the chunk value did not reach BOTH containers. run-server.sh (the MTP0 path) did not
# forward this variable until today; the patched code defaults to 32 when it is absent.
verify_chunk() {
  local root=$1 want=$2 lane ok=1
  for lane in ladder ladder-mtp0; do
    if grep -q "\"VLLM_XPU_FP16_LINEAR_ROWCHUNK=${want}\"" "${root}/${lane}/container-inspect.json" 2>/dev/null; then
      log "$(basename "${root}") ${lane}: VLLM_XPU_FP16_LINEAR_ROWCHUNK=${want} verified in container env"
    else
      log "$(basename "${root}") ${lane}: VLLM_XPU_FP16_LINEAR_ROWCHUNK=${want} NOT in container env - arm is not what it claims"; ok=0
    fi
  done
  [[ ${ok} == 1 ]]
}
arm() {
  local label=$1 chunk=$2; shift 2
  local root=${out}/qwen35-4b-w4a16-20260909-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting (chunk=${chunk}) -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 DEPTH=3 STAGES="ladders" \
      VLLM_XPU_FP16_LINEAR_ROWCHUNK="${chunk}" "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  verify_chunk "${root}" "${chunk}" || { echo "knob not applied in ${label}" >"${out}/qwen35-4b-rowchunk-20260909-STOPPED"; return 1; }
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-rowchunk-20260909-STOPPED"; return 1
  fi
  return 0
}

# y1: x2's exact configuration with the chunk off.
arm y1 0 TP=1 LADDER_CONCURRENCY="32,36,40,44,48,56,64" LADDER_REPEATS=10 \
    CAPTURE_SIZES="1,2,4,8,16,24,32,36,40,44,48,52,56,60,64" CAPTURE_MAX=64 || exit 1

# y2: the prediction past c64 with the chunk on. max_num_seqs 128 so c96 can fill; every rung captured.
arm y2 32 TP=1 LADDER_CONCURRENCY="64,68,72,80,96" LADDER_REPEATS=10 LADDER_MNS=128 \
    CAPTURE_SIZES="1,2,4,8,16,32,64,68,72,80,96" CAPTURE_MAX=96 || exit 1

# y3: does the exact recipe survive the chunk change? Same shape as g3/r3 (fragile suite, c64, 20
# passes, 5 ms stagger), chunk off.
arm y3 0 TP=1 LADDER_CONCURRENCY="64" LADDER_REPEATS=20 \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" || exit 1

log "=== chain 11 complete ==="
echo done >"${out}/qwen35-4b-rowchunk-20260909-DONE"
