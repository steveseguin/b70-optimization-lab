#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 14 (2026-09-11): R291, the verified class-consistent FP16 linear, end to end.
#
# Chain 13 (R290) removed the tax above c16 and passed the strict gates, but lost MTP0 exactness on one
# card from c20 up and cost 12% at single user. Offline the op was exact for every shape; the census was
# the fault (a one-input row-0 fingerprint merged kernels), and the pad path allocated per call. R291
# fingerprints on three inputs, verifies each class for determinism and position/pad invariance before it
# can be canonical, falls back to R224 pieces otherwise, and pads from persistent buffers. Same arms as
# chain 13 so every number is directly comparable: q1/q2 ladders, q5 the stagger recipe, q3/q4 strict,
# q6/q7 high rungs, q8/q9 depths 2 and 4.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-classpad2-20260911-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json
image=neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-verified-r291
image_id=sha256:4f97c2399227c40367879ace167ec8e194c3e53a70e96ddae5630e78c94c50d8

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-classpad2-20260911.pid"
log() { printf '[classpad2 %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || { log "image id mismatch"; exit 1; }
# Queue behind chain 11 and the 9B drift probe (its container is unnamed, so wait for its DONE file).
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
hardware_abort() {
  [[ -f "$1/ABORTED" ]] || return 1
  grep -qiE 'not in normal state|fault signature|compute/XCCL health|container is still running|did not become healthy' "$1/ABORTED"
}
verify_classpad() {  # every server this arm launched must carry the env AND have logged its census map
  local root=$1 d n=0 ok=1
  for d in "${root}"/*/; do
    [[ -e "${d}container-inspect.json" ]] || continue; n=$((n+1))
    grep -q '"VLLM_XPU_FP16_LINEAR_CLASSPAD=1"' "${d}container-inspect.json" || { log "$(basename "${root}")/$(basename "$d"): CLASSPAD=1 NOT in container env"; ok=0; }
    grep -q 'R291 classpad census.*verdict=classpad' "${d}server.log" 2>/dev/null || { log "$(basename "${root}")/$(basename "$d"): no R290 census line in server.log"; ok=0; }
  done
  [[ ${n} -gt 0 ]] || { log "$(basename "${root}"): no container records"; ok=0; }
  [[ ${ok} == 1 ]] && log "$(basename "${root}"): classpad verified in ${n} server(s): $(grep -ho 'R291 classpad census shape=[0-9x]* .*map=[^ ]* [^ ]*' "${root}"/*/server.log | sort -u | head -2 | tr '\n' ';')"
  [[ ${ok} == 1 ]]
}
arm() {
  local label=$1; shift
  local root=${out}/qwen35-4b-w4a16-20260911-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      IMAGE="${image}" IMAGE_ID="${image_id}" VLLM_XPU_FP16_LINEAR_CLASSPAD=1 \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  verify_classpad "${root}" || { echo "knob not applied in ${label}" >"${out}/qwen35-4b-classpad2-20260911-STOPPED"; return 1; }
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-classpad2-20260911-STOPPED"; return 1
  fi
  return 0
}

low="1,2,4,8,12,16,20,24,32,64"
hi_caps="1,2,4,8,16,20,24,32,40,48,56,64,80,96,112,128"
# p1: TP1 identity ladders, engine defaults - the matrix rows and the MTP0 exactness read.
arm q1 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
# p5: the exact recipe under R290 - fragile suite, c64, 20 passes, 5 ms stagger (compare r3, x3, y3).
arm q5 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" || exit 1
# p3/p4: the strict gates on both topologies - the headline under R290.
arm q3 TP=1 DEPTH=3 STAGES="strict" || exit 1
arm q2 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
arm q4 TP=2 DEPTH=3 STAGES="strict" || exit 1
# p6/p7: the high rungs with f4's settings.
arm q6 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1
arm q7 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1
# p8/p9: the depth axis, which the R224 tax biased toward shallow depths.
arm q8 TP=1 DEPTH=2 STAGES="ladders" LADDER_CONCURRENCY="1,4,8,16,32,64" LADDER_REPEATS=4 || exit 1
arm q9 TP=1 DEPTH=4 STAGES="ladders" LADDER_CONCURRENCY="1,4,8,16,32,64" LADDER_REPEATS=4 || exit 1

log "=== chain 14 complete ==="
echo done >"${out}/qwen35-4b-classpad2-20260911-DONE"
