#!/usr/bin/env bash
# Rebase onto vLLM v0.29.0: the published concurrency-identity recipe on the R301 candidate, 4B, one card, queued behind the
# 32K ladder: (a) no speculation, CLASSPAD=1, fragile suite c64 x 5 passes with the 5 ms admission stagger (served R293:
# 1280/1280 at 2104 tok/s); (b) depth 3, CLASSPAD=1, c64 x 2 (served R293: 1831 tok/s). Also the c128 no-spec rung.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/rebase-v0290-identity-20260912-wrapper.log
model=/home/steve/llm-models/qwen35-4b-w4a16; manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json
image=rebase/vllm-xpu:v0290-stage-b1; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000 SKIP_IMAGE_CONTRACT=1 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt VLLM_XPU_FP16_LINEAR_CLASSPAD=1
log() { printf '[rebase-id %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
until [[ -e ${out}/rebase-v0290-depth32k-20260912-DONE ]]; do sleep 30; done
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 30; done; sleep 10; }
arm() { local run=$1 depth=$2 conc=$3 reps=$4; shift 4; local root=${out}/qwen35-4b-w4a16-20260912-${run}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${run}: root used"; return; }
  wait_free; log "${run}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" \
      ROOT="${root}" RUN="${run}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH="${depth}" STAGES="ladders" LADDER_CONCURRENCY="${conc}" LADDER_REPEATS="${reps}" "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${run}: engine exit $?"
  python3 - "${root}" <<'PY' | tee -a "${wrap}"
import json,glob,sys
for f in sorted(glob.glob(sys.argv[1]+'/ladder*/ladder.json')):
    d=json.load(open(f)); print('   ', f.split('/')[-2], [(b['concurrency'],b['repeat'],round(b['aggregate_tok_s_wall']),f"{b['oracle_exact_count']}/{b['oracle_exact_total']}") for b in d['batches']])
PY
}
arm rbid0 0 64 5 LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5"
arm rbid3 3 64 2 LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5"
arm rbid128 0 128 2
log "=== rebase identity chain complete ==="; echo done >"${out}/rebase-v0290-identity-20260912-DONE"
