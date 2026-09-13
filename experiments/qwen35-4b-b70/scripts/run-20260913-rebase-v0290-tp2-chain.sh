#!/usr/bin/env bash
# R304 two-card profiles (2026-09-13): 4B and 9B W4A16 TP2 strict pairs (published R294b-era TP2 headlines: 4B 240.9 strict
# depth 3 on R276-class arithmetic, 9B 164.7/93.6 depth3/MTP0) plus the no-spec c128 rung with CLASSPAD=1 (R293: 4B 4015,
# 9B 3227 tok/s, 512/512). Queued behind the 9B scheduled-draft chain; both cards.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/rebase-v0290-tp2-20260913-wrapper.log
image=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt
log() { printf '[rebase-tp2 %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
until [[ -e ${out}/qwen35-9b-dynsd-r305-20260913-DONE || -e ${out}/qwen35-9b-dynsd-r305-20260913-STOPPED ]]; do sleep 30; done
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 30; done; sleep 10; }
arm() { local lane=$1 model=$2 manifest=$3 run=$4 cp=$5 stages=$6; shift 6; local root=${out}/${lane}-20260913-${run}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${run}: root used"; return; }
  wait_free; log "${run}: starting -> ${root}"
  env LANE="${lane}" MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" VLLM_XPU_FP16_LINEAR_CLASSPAD="${cp}" \
      ROOT="${root}" RUN="${run}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=2 DEPTH=3 STAGES="${stages}" "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${run}: engine exit $?"; grep -E 'G[123] ' "${wrap}" | tail -3 | sed 's/^/    /'
}
m4=/home/steve/llm-models/qwen35-4b-w4a16; f4=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
m9=/home/steve/llm-models/qwen35-9b-w4a16; f9=${repo}/repro/qwen35-9b-w4a16-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json
arm qwen35-4b-w4a16 $m4 $f4 rt2 0 strict
arm qwen35-4b-w4a16 $m4 $f4 rt2c 1 ladders LADDER_CONCURRENCY=128 LADDER_REPEATS=2
arm qwen35-9b-w4a16 $m9 $f9 rt2 0 strict
arm qwen35-9b-w4a16 $m9 $f9 rt2c 1 ladders LADDER_CONCURRENCY=128 LADDER_REPEATS=2
log "=== rebase TP2 chain complete ==="; echo done >"${out}/rebase-v0290-tp2-20260913-DONE"
