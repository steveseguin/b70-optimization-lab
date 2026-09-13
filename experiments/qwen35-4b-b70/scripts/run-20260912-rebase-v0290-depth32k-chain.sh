#!/usr/bin/env bash
# Rebase onto vLLM v0.29.0: the 2K-32K real-content exact-depth ladder (engine stage depth32k: MTP0 arm as oracle, then the
# depth-3 arm) on the stage-B1 image for the 4B, one card; queued behind the 27B strict chain. The served R294b/R293 recipe
# is 18/18 byte-exact at 32K; kernels 0.1.14.1 carry upstream #544 (GDN conv-state fix at block boundaries), so this is the
# stage that would show a behaviour change if the fix altered anything on this model.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/rebase-v0290-depth32k-20260912-wrapper.log
image=rebase/vllm-xpu:v0290-stage-b1; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000 SKIP_IMAGE_CONTRACT=1 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt VLLM_XPU_FP16_LINEAR_CLASSPAD=0
log() { printf '[rebase-32k %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
until [[ -e ${out}/qwen38-int4-rebase-v0290-20260912-DONE ]]; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 30; done; sleep 10
root=${out}/qwen35-4b-w4a16-20260912-rb32k
[[ -e "${root}/campaign-start.txt" ]] && { log "root used"; exit 0; }
log "starting -> ${root}"
env LANE=qwen35-4b-w4a16 MODEL_DIR=/home/steve/llm-models/qwen35-4b-w4a16 MODEL_MANIFEST=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json \
    QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" ROOT="${root}" RUN=rb32k DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="depth32k" bash "${engine}" >>"${wrap}" 2>&1
log "engine exit $?"; grep -E 'depth32k|exact|32k' "${wrap}" | tail -4 | sed 's/^/    /'
log "=== rebase depth32k complete ==="; echo done >"${out}/rebase-v0290-depth32k-20260912-DONE"
