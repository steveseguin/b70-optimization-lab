#!/usr/bin/env bash
# 4B, 2026-09-12: does torch deterministic mode (R295) change identity under speculation? The census found the default
# oneDNN fp16 GEMM run-to-run nondeterministic for the per-layer out-projection at 129+ rows - exactly the row counts a
# depth-3 c64 verify step produces. Two arms on R295, one card, depth 3, CLASSPAD=1, default 67k shortlist, fragile
# suite c64 x 20 with the 5 ms stagger: det1 (VLLM_XPU_TORCH_DETERMINISTIC=1) then det0. Queued behind the upstream
# reproductions (upstream-repro-20260912/queue-DONE).
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/qwen35-4b-torchdet-20260912-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16; manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json
image=neural-download/vllm-openai-xpu:qwen38-int4-xpu-torch-deterministic-r295; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000
log() { printf '[torchdet %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
until [[ -e ${out}/upstream-repro-20260912/queue-DONE ]]; do sleep 30; done
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|upstream-'; do sleep 30; done; sleep 10; }
for arm in det1 det0; do
  root=${out}/qwen35-4b-w4a16-20260912-${arm}; val=${arm#det}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${arm}: root already used, skipping"; continue; }
  wait_free; log "${arm}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" \
      VLLM_XPU_FP16_LINEAR_CLASSPAD=1 VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt VLLM_XPU_TORCH_DETERMINISTIC="${val}" \
      ROOT="${root}" RUN="${arm}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64" LADDER_REPEATS=20 \
      LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" bash "${engine}" >>"${wrap}" 2>&1
  log "${arm}: engine exit $?"
  for d in ladder ladder-mtp0; do grep -q "\"VLLM_XPU_TORCH_DETERMINISTIC=${val}\"" "${root}/${d}/container-inspect.json" && log "${arm}/${d}: env verified" || log "${arm}/${d}: env NOT in container"; [[ "${val}" == 1 ]] && { grep -q 'R295: torch.use_deterministic_algorithms' "${root}/${d}/server.log" && log "${arm}/${d}: R295 active" || log "${arm}/${d}: R295 line MISSING"; }; done
done
log "=== torchdet chain complete ==="; echo done >"${out}/qwen35-4b-torchdet-20260912-DONE"
