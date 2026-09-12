#!/usr/bin/env bash
# Qwen3.5-4B W4A16, 2026-09-12: the shortlisted draft head (R294). One card, depth 3, INT4 draft head, CLASSPAD=0
# (the published single-user path), strict stage only: each arm is its own MTP0 pair and depth-3 pair on fresh servers,
# so G2/G3 prove the shortlist changed no output and the depth-3 pair gives the single-user rate. Arms: shortlists of
# the top 32768, 16384, 8192 and 65536 (= all 38,662 tokens the corpus uses) most frequent tokens, then the same image
# with no shortlist as the in-image control (expected = the published 177.4 / 177.2).
set -uo pipefail
repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-shortlist-20260912-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
image=neural-download/vllm-openai-xpu:qwen38-int4-draft-head-shortlist-r294
image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000
echo $$ >"${out}/qwen35-4b-shortlist-20260912.pid"
log() { printf '[shortlist %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10; }
arm() {
  local label=$1 sl=$2
  local root=${out}/qwen35-4b-w4a16-20260912-${label}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${label}: root already used, skipping"; return 0; }
  wait_free
  log "${label}: starting -> ${root} (shortlist='${sl}')"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
      IMAGE="${image}" IMAGE_ID="${image_id}" VLLM_XPU_FP16_LINEAR_CLASSPAD=0 VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST="${sl}" \
      ROOT="${root}" RUN="${label}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="strict" \
      bash "${engine}" >>"${wrap}" 2>&1
  log "${label}: engine exit $?"
  if [[ -n "${sl}" ]]; then
    local d ok=1
    for d in "${root}"/mtp3-*/; do
      grep -q "\"VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=${sl}\"" "${d}container-inspect.json" 2>/dev/null || { log "$(basename "$d"): shortlist env NOT in container"; ok=0; }
      grep -q 'R294 draft shortlist' "${d}server.log" 2>/dev/null || { log "$(basename "$d"): no R294 shortlist line in server.log"; ok=0; }
    done
    [[ ${ok} == 1 ]] && log "${label}: shortlist verified: $(grep -ho 'R294 draft shortlist: [^,]*, [0-9]* in this shard' "${root}"/mtp3-a/server.log | head -1)"
    [[ ${ok} == 1 ]] || { echo "knob not applied in ${label}" >"${out}/qwen35-4b-shortlist-20260912-STOPPED"; return 1; }
  fi
  grep -qiE 'not in normal state|fault signature|did not become healthy' "${root}/ABORTED" 2>/dev/null && { log "${label}: HARDWARE abort"; echo "stopped after ${label}" >"${out}/qwen35-4b-shortlist-20260912-STOPPED"; return 1; }
  return 0
}
arm sl32k /opt/draft-shortlists/shortlist-top32768.txt || exit 1
arm sl16k /opt/draft-shortlists/shortlist-top16384.txt || exit 1
arm sl8k  /opt/draft-shortlists/shortlist-top8192.txt  || exit 1
arm sl64k /opt/draft-shortlists/shortlist-top65536.txt || exit 1
arm slbase "" || exit 1
log "=== shortlist chain complete ==="; echo done >"${out}/qwen35-4b-shortlist-20260912-DONE"
