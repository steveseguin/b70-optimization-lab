#!/usr/bin/env bash
# Qwen3.5-4B W4A16 chain 13 (2026-09-09): the R290 class-consistent FP16 linear, measured end to end.
#
# The census (scripts/fp16-linear-mclass-census*.py) showed the oneDNN fp16 GEMM at the vocabulary shape
# has four M-classes (1-32, 33-128, 129-320, 321-512), each position-invariant, pad-invariant and
# deterministic. R224 keeps every call in class 1-32 by re-reading the 1.2 GB weight once per 32 rows
# (y1: a 25-54% tax above 32 rows). R290 pads or splits every call into the most populous class instead,
# so one user and sixty-four compute bit-identical rows at ~0.1 ms per step on a single row. Offline it is
# bit-exact at every M for the TP1 and TP2 lm_head shapes and the mtp.fc shape. This chain measures it on
# the server: identity ladders, the strict gates, the stagger recipe, the high rungs and the depth axis.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-classpad-20260909-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json
image=neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-r290
image_id=sha256:fe23db2fd9aaf25daffd1a209ad72839b89d7f683ab7f6555ccbf5d505418eb5

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-classpad-20260909.pid"
log() { printf '[classpad %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }

[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || { log "image id mismatch"; exit 1; }
# Queue behind chain 11 and the 9B drift probe (its container is unnamed, so wait for its DONE file).
until [[ -e ${out}/drift-queued-20260909-DONE ]]; do sleep 30; done
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
    grep -q 'R290 classpad census' "${d}server.log" 2>/dev/null || { log "$(basename "${root}")/$(basename "$d"): no R290 census line in server.log"; ok=0; }
  done
  [[ ${n} -gt 0 ]] || { log "$(basename "${root}"): no container records"; ok=0; }
  [[ ${ok} == 1 ]] && log "$(basename "${root}"): classpad verified in ${n} server(s): $(grep -ho 'R290 classpad census shape=[0-9x]* .*map=[^ ]* [^ ]*' "${root}"/*/server.log | sort -u | head -2 | tr '\n' ';')"
  [[ ${ok} == 1 ]]
}
arm() {
  local label=$1; shift
  local root=${out}/qwen35-4b-w4a16-20260909-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      IMAGE="${image}" IMAGE_ID="${image_id}" VLLM_XPU_FP16_LINEAR_CLASSPAD=1 \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  verify_classpad "${root}" || { echo "knob not applied in ${label}" >"${out}/qwen35-4b-classpad-20260909-STOPPED"; return 1; }
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-4b-classpad-20260909-STOPPED"; return 1
  fi
  return 0
}

low="1,2,4,8,12,16,20,24,32,64"
hi_caps="1,2,4,8,16,20,24,32,40,48,56,64,80,96,112,128"
# p1: TP1 identity ladders, engine defaults - the matrix rows and the MTP0 exactness read.
arm p1 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
# p5: the exact recipe under R290 - fragile suite, c64, 20 passes, 5 ms stagger (compare r3, x3, y3).
arm p5 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" || exit 1
# p3/p4: the strict gates on both topologies - the headline under R290.
arm p3 TP=1 DEPTH=3 STAGES="strict" || exit 1
arm p2 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
arm p4 TP=2 DEPTH=3 STAGES="strict" || exit 1
# p6/p7: the high rungs with f4's settings.
arm p6 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1
arm p7 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1
# p8/p9: the depth axis, which the R224 tax biased toward shallow depths.
arm p8 TP=1 DEPTH=2 STAGES="ladders" LADDER_CONCURRENCY="1,4,8,16,32,64" LADDER_REPEATS=4 || exit 1
arm p9 TP=1 DEPTH=4 STAGES="ladders" LADDER_CONCURRENCY="1,4,8,16,32,64" LADDER_REPEATS=4 || exit 1

log "=== chain 13 complete ==="
echo done >"${out}/qwen35-4b-classpad-20260909-DONE"
