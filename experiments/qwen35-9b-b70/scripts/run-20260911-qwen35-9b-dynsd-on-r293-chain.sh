#!/usr/bin/env bash
# Qwen3.5-9B W4A16: the scheduled-draft server (repro/qwen35-9b-w4a16-b70/docker overlays: dynamic Mamba
# allocation, full decode graphs per scheduled K, draft-state catch-up) combined with the class-consistent FP16
# linear (R293, VLLM_XPU_FP16_LINEAR_CLASSPAD=1), 2026-09-11. The overlays touch scheduler/model-runner/proposer
# files; R293 touches model_executor/layers/utils.py; no overlap, so the same three COPY-only Dockerfiles were
# rebuilt FROM the R293 image (docker/r293-*.Dockerfile). Two arms on this host, each a full run (strict pairs
# with the schedule, MTP0 oracle pair, four-pass c1-c64 ladders on both profiles):
#   dyn293  R293 overlays, CLASSPAD=1   - the candidate
#   dyn276  R276 overlays, CLASSPAD=0   - the published scheduled-draft configuration, same host, same day
# Schedule [[1,8,3],[9,16,1],[17,64,0]] as published (depth 3 to 8 users, 1 to 16, none above).
set -uo pipefail
repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-9b-dynsd-r293-20260911-wrapper.log
model=/home/steve/llm-models/qwen35-9b-w4a16
manifest=${repo}/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json
schedule='[[1,8,3],[9,16,1],[17,64,0]]'
export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-9b-dynsd-r293-20260911.pid"
log() { printf '[dynsd %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
# The dynamic launcher's content pins (sha256 of the overlaid files), checked here because the engine
# launches the strict launchers directly rather than through that launcher.
declare -A want=(
  [v1/core/sched/scheduler.py]=6d550a8e6a5c6abf200d66fbc4fc45c8ce371a312d454c39e057a45b364994c3
  [v1/core/single_type_kv_cache_manager.py]=b9a100331f98882dc01dc6f6efac53b1fc1fc949ba0b8915e932336a8a521c09
  [config/vllm.py]=e03067d4fbcf56ae51fd254fb70c02a3cdf25fd3db6bae70855b945cdc15bcb2
  [v1/cudagraph_dispatcher.py]=3d296446deea8726643d7942f49cf920b82d26bb2205480190ef4d0a731bbb98
  [v1/worker/gpu_model_runner.py]=977887edddf87d38aec35905d9668634da461ff6dc39a5b2301889a2228f4ecb
  [v1/spec_decode/llm_base_proposer.py]=2e0f1661bb02a05297edcc5de586eacc20700a997074197988e1923d69ffd03d
)
verify_overlay() {
  local image=$1 probe=qwen35-overlay-probe-$$ rel got ok=1
  docker create --name "${probe}" "${image}" >/dev/null || return 1
  for rel in "${!want[@]}"; do
    got=$(docker cp "${probe}:/opt/venv/lib/python3.12/site-packages/vllm/${rel}" - | tar -xO | sha256sum | cut -d' ' -f1)
    [[ "${got}" == "${want[$rel]}" ]] || { log "overlay content mismatch in ${image}: ${rel} is ${got}"; ok=0; }
  done
  docker rm "${probe}" >/dev/null 2>&1 || true
  [[ ${ok} == 1 ]] && log "overlay content verified in ${image}"
  [[ ${ok} == 1 ]]
}
verify_classpad() {  # every server must carry the requested CLASSPAD value; census lines only when on
  local root=$1 want_cp=$2 d n=0 ok=1
  for d in "${root}"/*/; do
    [[ -e "${d}container-inspect.json" ]] || continue; n=$((n+1))
    grep -q "\"VLLM_XPU_FP16_LINEAR_CLASSPAD=${want_cp}\"" "${d}container-inspect.json" || { log "$(basename "${root}")/$(basename "$d"): CLASSPAD=${want_cp} NOT in container env"; ok=0; }
    if [[ "${want_cp}" == 1 ]]; then grep -q 'R291 classpad census.*verdict=classpad' "${d}server.log" 2>/dev/null || { log "$(basename "${root}")/$(basename "$d"): no classpad census line"; ok=0; }; fi
  done
  [[ ${n} -gt 0 && ${ok} == 1 ]] && log "$(basename "${root}"): CLASSPAD=${want_cp} verified in ${n} server(s)"
  [[ ${n} -gt 0 && ${ok} == 1 ]]
}
arm() {
  local label=$1 image=$2 cp=$3; shift 3
  local root=${out}/qwen35-9b-w4a16-20260911-${label}
  local image_id; image_id=$(docker image inspect "${image}" --format '{{.Id}}') || { log "${label}: image missing"; return 1; }
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  verify_overlay "${image}" || return 1
  wait_free
  log "${label}: starting -> ${root} (${image} ${image_id:0:19}, CLASSPAD=${cp})"
  env LANE=qwen35-9b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      IMAGE="${image}" IMAGE_ID="${image_id}" VLLM_XPU_FP16_LINEAR_CLASSPAD="${cp}" SPEC_SCHEDULE="${schedule}" \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="strict ladders" \
      LADDER_REPEATS=4 "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  verify_classpad "${root}" "${cp}" || { echo "knob not applied in ${label}" >"${out}/qwen35-9b-dynsd-r293-20260911-STOPPED"; return 1; }
  grep -qiE 'not in normal state|fault signature|did not become healthy' "${root}/ABORTED" 2>/dev/null && { log "${label}: HARDWARE abort"; echo "stopped after ${label}" >"${out}/qwen35-9b-dynsd-r293-20260911-STOPPED"; return 1; }
  return 0
}
arm dyn293 neural-download/vllm-openai-xpu:qwen38-int4-r293-dynsd-catchup 1 || exit 1
arm dyn276 neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-catchup 0 || exit 1
log "=== dynsd-on-R293 chain complete ==="; echo done >"${out}/qwen35-9b-dynsd-r293-20260911-DONE"
