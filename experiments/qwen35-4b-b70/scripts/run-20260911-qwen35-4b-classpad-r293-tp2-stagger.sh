#!/usr/bin/env bash
# Chain 16 (2026-09-11): the deployable two-card recipe on R293 - TP2, no speculation, 5 ms stagger, fragile
# suite, c64, 20 passes (the shape of w1/w2, which gave 1280/1280 at 2711 tok/s under R224). Queued behind
# chain 15. Reuses chain 15's arm() by sourcing nothing: a one-arm copy with its own wrapper.
set -uo pipefail
repo=/home/steve/b70-optimization-lab
engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results
wrap=${out}/qwen35-4b-classpad4-20260911-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16
manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json
image=neural-download/vllm-openai-xpu:qwen38-int4-fp16-linear-classpad-cheapest-r293
image_id=sha256:40d46730c9a24f9396cc67c0e5578dd80d11dfae7a4d23a55f97620140a0b3e6
export LOAD_MEMORY_MIB=7000
log() { printf '[classpad4 %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
until [[ -e ${out}/qwen35-4b-classpad3-20260911-DONE || -e ${out}/qwen35-4b-classpad3-20260911-STOPPED ]]; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]'; do sleep 30; done; sleep 10
root=${out}/qwen35-4b-w4a16-20260911-r10
log "r10: starting -> ${root}"
env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors \
    IMAGE="${image}" IMAGE_ID="${image_id}" VLLM_XPU_FP16_LINEAR_CLASSPAD=1 \
    ROOT="${root}" RUN=r10 DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=2 DEPTH=3 STAGES="ladders" \
    LADDER_CONCURRENCY="64" LADDER_REPEATS=20 LADDER_SUITE="${fragile}" \
    LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5" bash "${engine}" >>"${wrap}" 2>&1
log "r10: engine exit $?"
for d in "${root}"/*/; do [[ -e "${d}container-inspect.json" ]] || continue
  grep -q '"VLLM_XPU_FP16_LINEAR_CLASSPAD=1"' "${d}container-inspect.json" && grep -q 'R291 classpad census.*verdict=classpad' "${d}server.log" && log "r10/$(basename "$d"): classpad verified" || log "r10/$(basename "$d"): classpad NOT verified"; done
log "=== chain 16 complete ==="; echo done >"${out}/qwen35-4b-classpad4-20260911-DONE"
