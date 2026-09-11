#!/usr/bin/env bash
# Qwen3.5-9B W4A16 classpad chain (2026-09-11): R293 on the 9B lane.
#
# The 4B lane found that the R224 32-row FP16 linear chunk re-reads the vocabulary projection once per
# piece (25-54% of throughput above 32 rows) and that R293's class-consistent pad removes the tax while
# staying lossless by every gate (experiments/qwen35-4b-b70/notes/2026-09-11-r293-*.md). The 9B runs the
# same op on the same base image with a 2 GB fp16 projection (248320 x 4096), so the tax should be larger.
# Arms: s1/s2 identity ladders TP1/TP2 (engine defaults), s3/s4 strict gates, s5 the two-card stagger
# recipe on this lane's fragile tie-site suite (never measured on the 9B), s6/s7 high rungs with the
# f4-style settings. Baselines: x1 (TP1 ladder), the identitypower/fragile TP2 arms, w1/w3 strict.
set -uo pipefail

repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-9b-classpad-20260911-wrapper.log
model=/home/steve/llm-models/qwen35-9b-w4a16
manifest=${repo}/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json
fragile=${repo}/experiments/qwen35-9b-b70/data/2026-09-08-fragile-tie-site-suite-v1.json
image=neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-cheapest-r293
image_id=sha256:40d46730c9a24f9396cc67c0e5578dd80d11dfae7a4d23a55f97620140a0b3e6

export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-9b-classpad-20260911.pid"
log() { printf '[9b-classpad %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
[[ "$(docker image inspect "${image}" --format '{{.Id}}')" == "${image_id}" ]] || { log "image id mismatch"; exit 1; }
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
hardware_abort() {
  [[ -f "$1/ABORTED" ]] || return 1
  grep -qiE 'not in normal state|fault signature|compute/XCCL health|container is still running|did not become healthy' "$1/ABORTED"
}
verify_classpad() {
  local root=$1 d n=0 ok=1
  for d in "${root}"/*/; do
    [[ -e "${d}container-inspect.json" ]] || continue; n=$((n+1))
    grep -q '"VLLM_XPU_FP16_LINEAR_CLASSPAD=1"' "${d}container-inspect.json" || { log "$(basename "${root}")/$(basename "$d"): CLASSPAD=1 NOT in container env"; ok=0; }
    grep -q 'R291 classpad census.*verdict=classpad' "${d}server.log" 2>/dev/null || { log "$(basename "${root}")/$(basename "$d"): no classpad census line in server.log"; ok=0; }
  done
  [[ ${n} -gt 0 ]] || { log "$(basename "${root}"): no container records"; ok=0; }
  [[ ${ok} == 1 ]] && log "$(basename "${root}"): classpad verified in ${n} server(s): $(grep -ho 'R291 classpad census shape=[0-9x]* .*verdict=[a-z0-9-]*' "${root}"/*/server.log | sort -u | head -3 | tr '\n' ';')"
  [[ ${ok} == 1 ]]
}
arm() {
  local label=$1; shift
  local root=${out}/qwen35-9b-w4a16-20260911-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting -> ${root}"
  env LANE=qwen35-9b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      IMAGE="${image}" IMAGE_ID="${image_id}" VLLM_XPU_FP16_LINEAR_CLASSPAD=1 \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 "$@" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  verify_classpad "${root}" || { echo "knob not applied in ${label}" >"${out}/qwen35-9b-classpad-20260911-STOPPED"; return 1; }
  if hardware_abort "${root}"; then
    log "${label}: HARDWARE abort -> stopping"; echo "stopped after ${label}" >"${out}/qwen35-9b-classpad-20260911-STOPPED"; return 1
  fi
  return 0
}

low="1,2,4,8,12,16,20,24,32,64"
hi_caps="1,2,4,8,16,20,24,32,40,48,56,64,80,96,112,128"
arm s1 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
arm s3 TP=1 DEPTH=3 STAGES="strict" || exit 1
arm s2 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="${low}" LADDER_REPEATS=4 || exit 1
arm s4 TP=2 DEPTH=3 STAGES="strict" || exit 1
arm s5 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 \
    LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" || exit 1
arm s6 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1
arm s7 TP=2 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=4 LADDER_MNS=128 LADDER_MBT=1024 \
    CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 || exit 1

log "=== 9B classpad chain complete ==="
echo done >"${out}/qwen35-9b-classpad-20260911-DONE"
