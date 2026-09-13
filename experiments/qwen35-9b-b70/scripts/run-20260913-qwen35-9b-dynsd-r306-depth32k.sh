#!/usr/bin/env bash
# 9B scheduled-draft server on R306: the 2K-32K real-content exact-depth ladder (engine stage depth32k: no-spec oracle arm,
# then the scheduled arm), one card, real contract. Published profile (cudynm1 on R276): 18/18 exact.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/qwen35-9b-dynsd-r306-depth32k-20260913-wrapper.log
image=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r306-dynsd; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt VLLM_XPU_FP16_LINEAR_CLASSPAD=1
log() { printf '[dyn306-32k %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 30; done; sleep 10
root=${out}/qwen35-9b-w4a16-20260913-dyn306-32k
[[ -e "${root}/campaign-start.txt" ]] && { log "root used"; exit 0; }
log "starting -> ${root}"
env LANE=qwen35-9b-w4a16 MODEL_DIR=/home/steve/llm-models/qwen35-9b-w4a16 MODEL_MANIFEST=${repo}/repro/qwen35-9b-w4a16-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json \
    QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" SPEC_SCHEDULE='[[1,8,3],[9,16,1],[17,64,0]]' ROOT="${root}" RUN=dyn306-32k DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="depth32k" bash "${engine}" >>"${wrap}" 2>&1
log "engine exit $?"; grep -E 'PASS|FAIL' "${wrap}" | tail -2 | sed 's/^/    /'
log "=== dyn306 depth32k complete ==="; echo done >"${out}/qwen35-9b-dynsd-r306-depth32k-20260913-DONE"
