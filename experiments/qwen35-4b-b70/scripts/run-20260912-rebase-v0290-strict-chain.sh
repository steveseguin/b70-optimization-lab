#!/usr/bin/env bash
# Rebase onto vLLM v0.29.0 (2026-09-12 evening): strict lossless gates (G1 MTP0 a/b, G2 depth-3 a/b, G3 depth-3 vs MTP0)
# on the stage-B1 image (v0.29.0 + ported overlays + kernels 0.1.14.1 with oneDNN r137a/r137b/r221) for the 4B and 9B
# W4A16 lanes, one card each, served configuration (draft INT4 head + 67k shortlist, CLASSPAD=0), V1 model runner pinned.
# The image is not under the recipe contract yet: SKIP_IMAGE_CONTRACT=1 (loud) and EXPECTED_KERNEL_HEAD = kernels 0.1.14.1.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/rebase-v0290-strict-20260912-wrapper.log
image=rebase/vllm-xpu:v0290-stage-b1; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000 SKIP_IMAGE_CONTRACT=1 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt VLLM_XPU_FP16_LINEAR_CLASSPAD=0
log() { printf '[rebase-strict %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|upstream-|rebase-'; do sleep 30; done; sleep 10; }
run_lane() { local lane=$1 model=$2 manifest=$3 run=$4; local root=${out}/${lane}-20260912-${run}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${run}: root used, skipping"; return; }
  wait_free; log "${run}: starting -> ${root}"
  env LANE="${lane}" MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" \
      ROOT="${root}" RUN="${run}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="strict" bash "${engine}" >>"${wrap}" 2>&1
  log "${run}: engine exit $?"; grep -E 'G[123] ' "${wrap}" | tail -3 | sed 's/^/    /'
  for d in mtp0-a mtp3-a; do grep -q 'Using V1 Model Runner\|Prepared MTP draft-only INT4' "${root}/${d}/server.log" 2>/dev/null && log "${run}/${d}: V1 runner / draft head verified" || log "${run}/${d}: check server.log"; done
}
run_lane qwen35-4b-w4a16 /home/steve/llm-models/qwen35-4b-w4a16 ${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json rb1
run_lane qwen35-9b-w4a16 /home/steve/llm-models/qwen35-9b-w4a16 ${repo}/repro/qwen35-9b-w4a16-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json rb1
log "=== rebase strict chain complete ==="; echo done >"${out}/rebase-v0290-strict-20260912-DONE"
