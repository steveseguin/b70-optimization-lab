#!/usr/bin/env bash
# 4B, 2026-09-12: the 92k-row draft shortlist under many users. One card, depth 3, CLASSPAD=1 (the many-user mode),
# c1-c64 ladders on both profiles, four passes; compare with r1 (R293, no shortlist). Queued behind the 9B chain.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/qwen35-4b-shortlist3-20260912-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16; manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
image=neural-download/vllm-openai-xpu:qwen38-int4-draft-head-shortlist-r294b; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000
log() { printf '[shortlist3 %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
until [[ -e ${out}/qwen35-9b-shortlist-20260912-DONE || -e ${out}/qwen35-9b-shortlist-20260912-STOPPED ]]; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10
root=${out}/qwen35-4b-w4a16-20260912-slu92k-ladders
log "slu92k-ladders: starting -> ${root}"
env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" \
    VLLM_XPU_FP16_LINEAR_CLASSPAD=1 VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2all.txt \
    ROOT="${root}" RUN=slu92kl DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="1,2,4,8,12,16,20,24,32,64" LADDER_REPEATS=4 \
    bash "${engine}" >>"${wrap}" 2>&1
log "slu92k-ladders: engine exit $?"
grep -q 'R294 draft shortlist' "${root}/ladder/server.log" && log "shortlist verified in the ladder server" || log "NO shortlist line in the ladder server"
log "=== 4B shortlist ladders complete ==="; echo done >"${out}/qwen35-4b-shortlist3-20260912-DONE"
