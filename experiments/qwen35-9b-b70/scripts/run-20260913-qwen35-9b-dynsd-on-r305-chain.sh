#!/usr/bin/env bash
# Qwen3.5-9B W4A16: the scheduled-draft server on the v0.29.0 rebase (R305 = R304 + the three dynsd overlay diffs,
# 2026-09-13). One arm, the published configuration (schedule [[1,8,3],[9,16,1],[17,64,0]], CLASSPAD=1): strict pairs
# with the schedule, MTP0 oracle pair, four-pass c1-c64 ladders on both profiles. Reference: dyn293 (2026-09-11) c64
# 1631 tok/s, c16 960 exact, c32 1192 (120/128), one user 112.4; gates 12/12. R305 is not in the contract set yet
# (SKIP_IMAGE_CONTRACT=1, loud); its overlay content is pinned below from the built image. Queued behind the 27B r304c run.
set -uo pipefail
repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-9b-dynsd-r305-20260913-wrapper.log
model=/home/steve/llm-models/qwen35-9b-w4a16
manifest=${repo}/experiments/qwen35-9b-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json
schedule='[[1,8,3],[9,16,1],[17,64,0]]'
export LOAD_MEMORY_MIB=7000 SKIP_IMAGE_CONTRACT=1 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt
until grep -q 'r304c: engine exit' ${out}/qwen38-int4-rebase-v0290-20260912-wrapper.log 2>/dev/null; do sleep 30; done
log() { printf '[dynsd305 %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 30; done; sleep 10; }
declare -A want=(
  [v1/core/sched/scheduler.py]=09b8ed02301ad1d549619dc84a0b595639cac953a4c6ba8a3d5dca8f2b50c18a
  [v1/core/single_type_kv_cache_manager.py]=cd5442a9fb9dd14849a3b9de9c88c52b5533a18c0028ce859b8cbdf300de3cc8
  [config/vllm.py]=13d9ec1d9ca903064007bbd488954e0639a6fd1293f5fb55b06e380bff335b5d
  [v1/cudagraph_dispatcher.py]=3d296446deea8726643d7942f49cf920b82d26bb2205480190ef4d0a731bbb98
  [v1/worker/gpu_model_runner.py]=b7b491bc9686b7582cb38cdecb0356be133bc8f6c6e90fd813e02794cd88861f
  [v1/spec_decode/llm_base_proposer.py]=4f5638a47e5f57d697e97cbfb6a0c41f563b6d2f58c132fa7ecb5e132797ab64
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
  local root=${out}/qwen35-9b-w4a16-20260913-${label}
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
  verify_classpad "${root}" "${cp}" || { echo "knob not applied in ${label}" >"${out}/qwen35-9b-dynsd-r305-20260913-STOPPED"; return 1; }
  grep -qiE 'not in normal state|fault signature|did not become healthy' "${root}/ABORTED" 2>/dev/null && { log "${label}: HARDWARE abort"; echo "stopped after ${label}" >"${out}/qwen35-9b-dynsd-r305-20260913-STOPPED"; return 1; }
  return 0
}
arm dyn305 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r305-dynsd 1
log "=== dynsd R305 chain complete ==="; echo done >"${out}/qwen35-9b-dynsd-r305-20260913-DONE"
