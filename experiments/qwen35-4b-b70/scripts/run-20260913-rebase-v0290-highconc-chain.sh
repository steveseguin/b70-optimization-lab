#!/usr/bin/env bash
# R304 high-concurrency rungs with the SAME ladder settings the published R293 rows used (chain 15 r6/r7:
# LADDER_MNS=128 LADDER_MBT=1024, capture sizes to 128, c64/96/128), CLASSPAD=1, depth 3 (the engine runs the no-spec
# arm too). Published R293: 4B one card no-spec c128 2520 (512/512), two cards 4015 (512/512); 9B two cards 3227.
# The first TP2 chain's c128 rows used the engine defaults (mns 64, mbt 512) and are not comparable. Queued behind dyn306.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; wrap=${out}/rebase-v0290-highconc-20260913-wrapper.log
image=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
export LOAD_MEMORY_MIB=7000 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt VLLM_XPU_FP16_LINEAR_CLASSPAD=1
hi_caps="1,2,4,8,16,20,24,32,40,48,56,64,80,96,112,128"
log() { printf '[rebase-hc %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
until [[ -e ${out}/qwen35-9b-dynsd-r306-20260913-DONE || -e ${out}/qwen35-9b-dynsd-r306-20260913-STOPPED ]]; do sleep 30; done
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 30; done; sleep 10; }
arm() { local lane=$1 model=$2 manifest=$3 run=$4 tp=$5; local root=${out}/${lane}-20260913-${run}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${run}: root used"; return; }
  wait_free; log "${run}: starting -> ${root}"
  env LANE="${lane}" MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" \
      ROOT="${root}" RUN="${run}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP="${tp}" DEPTH=3 STAGES="ladders" LADDER_CONCURRENCY="64,96,128" LADDER_REPEATS=2 \
      LADDER_MNS=128 LADDER_MBT=1024 CAPTURE_SIZES="${hi_caps}" CAPTURE_MAX=128 bash "${engine}" >>"${wrap}" 2>&1
  log "${run}: engine exit $?"
  python3 - "${root}" <<'PY' | tee -a "${wrap}"
import json,glob,sys
for f in sorted(glob.glob(sys.argv[1]+'/ladder*/ladder.json')):
    d=json.load(open(f)); print('   ', f.split('/')[-2], [(b['concurrency'],b['repeat'],round(b['aggregate_tok_s_wall']),f"{b['oracle_exact_count']}/{b['oracle_exact_total']}") for b in d['batches']])
PY
}
m4=/home/steve/llm-models/qwen35-4b-w4a16; f4=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
m9=/home/steve/llm-models/qwen35-9b-w4a16; f9=${repo}/repro/qwen35-9b-w4a16-b70/manifests/model-direct-redhatai-qwen35-9b-w4a16-a398088c.json
arm qwen35-4b-w4a16 $m4 $f4 rhc1 1
arm qwen35-4b-w4a16 $m4 $f4 rhc2 2
arm qwen35-9b-w4a16 $m9 $f9 rhc1 1
arm qwen35-9b-w4a16 $m9 $f9 rhc2 2
log "=== rebase high-concurrency chain complete ==="; echo done >"${out}/rebase-v0290-highconc-20260913-DONE"
