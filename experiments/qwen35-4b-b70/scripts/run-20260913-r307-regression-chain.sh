#!/usr/bin/env bash
# R307 regression chain (2026-09-13): does the GDN state hand-off change anything on the normal path? 4B one card on the
# R307 candidate: (1) strict G1/G2/G3 for 4B and 9B via the strict chain (RB=r307), (2) 2K-32K real-content ladder, (3)
# c64 identity on the fragile suite (depth 3, 5 ms stagger), (4) the short-prompt alias harness (depth 3). Contract
# skipped (loud) because R307 changes three site-packages files pinned by the v0290 digest set. Queued behind the
# concurrent boundary chain.
set -Eeuo pipefail
repo=/home/steve/b70-optimization-lab; engine=${repo}/experiments/qwen35-9b-b70/scripts/run-20260907-qwen35-campaign.sh
out=/mnt/fast-ai/bench-results; R=${out}/rebase-v0290-20260912; wrap=${out}/r307-regression-20260913-wrapper.log
image=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r307; image_id=$(docker image inspect "${image}" --format '{{.Id}}')
model=/home/steve/llm-models/qwen35-4b-w4a16; manifest=${repo}/experiments/qwen35-4b-b70/manifests/model-direct-redhatai-qwen35-4b-w4a16-7a613872.json
fragile=${repo}/experiments/qwen35-4b-b70/data/2026-09-09-qwen35-4b-fragile-suite-c64.json
export LOAD_MEMORY_MIB=7000 SKIP_IMAGE_CONTRACT=1 EXPECTED_KERNEL_HEAD=6d92b1bfbf32767ecda8e819613eb151e70030ad VLLM_USE_V2_MODEL_RUNNER=0
export VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt VLLM_XPU_FP16_LINEAR_CLASSPAD=0
log() { printf '[r307-reg %s] %s\n' "$(date '+%m-%d %H:%M:%S')" "$*" | tee -a "${wrap}"; }
alias_pid=; name=; o=
fault_re='(xe [0-9a-f:.]+|drm\]).*(Fault response|CAT error|engine reset|gt reset|GPU reset|coredump|Timedout job|timed out|\bhung\b|wedged|device lost)|soft lockup'
alias_journal_check() {
  journalctl -k -b 0 --no-pager --since "$alias_start" >"$o/kernel-journal.txt"
  (grep -iE "$fault_re" "$o/kernel-journal.txt" | grep -vF 'Xe device coredump has been deleted.' || true) >"$o/kernel-fault-lines.txt"
  [[ ! -s "$o/kernel-fault-lines.txt" ]]
}
cleanup() {
  local rc=$?
  trap - EXIT
  if [[ -n "${alias_pid}" ]]; then
    docker logs "$name" >"$o/server.log" 2>&1 || true
    docker stop -t 60 "$name" >/dev/null 2>&1 || true
    wait "$alias_pid" 2>/dev/null || true
    docker rm -f "$name" >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap cleanup EXIT
until [[ -e ${R}/boundary-conc/DONE ]]; do sleep 30; done
trap 'rc=$?; log "ABORT: exit ${rc} at line ${LINENO}"; exit "$rc"' ERR
trap 'exit 130' INT
trap 'exit 143' TERM
wait_free() { while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 30; done; sleep 10; }
# (1) strict gates, 4B + 9B
wait_free; log "strict: starting"; IMAGE="${image}" RB=r307 bash ${repo}/experiments/qwen35-4b-b70/scripts/run-20260912-rebase-v0290-strict-chain.sh >>"${wrap}" 2>&1; log "strict: exit $?"
arm() { local run=$1 stages=$2 depth=$3; shift 3; local root=${out}/qwen35-4b-w4a16-20260913-${run}
  [[ -e "${root}/campaign-start.txt" ]] && { log "${run}: root already used; choose a fresh run"; return 2; }
  wait_free; log "${run}: starting -> ${root}"
  env LANE=qwen35-4b-w4a16 MODEL_DIR="${model}" MODEL_MANIFEST="${manifest}" QUANT=compressed-tensors IMAGE="${image}" IMAGE_ID="${image_id}" \
      ROOT="${root}" RUN="${run}" DRAFT_HEAD=1 W4A16_PAD=0 GRAPH=1 TP=1 DEPTH="${depth}" STAGES="${stages}" "$@" bash "${engine}" >>"${wrap}" 2>&1
  log "${run}: engine exit $?"
  python3 - "${root}" <<'PY' | tee -a "${wrap}"
import json,glob,sys
for f in sorted(glob.glob(sys.argv[1]+'/ladder*/ladder.json')):
    d=json.load(open(f)); print('   ', f.split('/')[-2], [(b['concurrency'],b['repeat'],round(b['aggregate_tok_s_wall']),f"{b['oracle_exact_count']}/{b['oracle_exact_total']}") for b in d['batches']])
PY
  (grep -E 'depth32k|PASS|FAIL' "${wrap}" || true) | tail -2 | sed 's/^/    /'
}
# (2) 2K-32K ladder, (3) c64 identity
arm r307-32k depth32k 3
arm r307-id3 ladders 3 VLLM_XPU_FP16_LINEAR_CLASSPAD=1 LADDER_CONCURRENCY=64 LADDER_REPEATS=2 LADDER_SUITE="${fragile}" LADDER_EXTRA_ARGS="--verbatim-prompts --launch-stagger-ms 5"
# (4) short prompts
wait_free; alias_start=$(date '+%Y-%m-%d %H:%M:%S'); o=${R}/alias-r307; mkdir -p $o; port=18175; name=rebase-alias-r307
( IMAGE=$image EXPECTED_IMAGE_ID=$image_id MODEL_DIR=$model PORT=$port CONTAINER_NAME=$name SERVED_MODEL_NAME=m VLLM_CACHE_DIR=$o/cache MTP_DEPTH=3 TENSOR_PARALLEL_SIZE=1 bash $repo/repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh > $o/launcher.log 2>&1 ) &
alias_pid=$!
log "alias: launched"; ready=0; for i in $(seq 1 150); do alias_journal_check || { log "ABORT: alias startup kernel fault"; exit 2; }; curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && { ready=1; break; }; kill -0 "$alias_pid" 2>/dev/null || break; sleep 10; done
[[ "$ready" == 1 ]] || { log "ABORT: alias server did not become healthy"; exit 2; }
python3 $repo/experiments/qwen35-4b-b70/probes/alias-harness-lab.py --base http://127.0.0.1:$port/v1 --model m --spec-tokens 3 --iters 30 --tag r307 > $o/harness.stdout 2>&1; log "alias: harness exit $?"
(grep -E '^(ALIAS|control|!!)' $o/harness.stdout || true) | cut -c1-120 | sed 's/^/    /' | tee -a "${wrap}"
docker logs $name > $o/server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 5; docker rm -f $name >/dev/null 2>&1
wait "$alias_pid" 2>/dev/null || true; alias_pid=
alias_journal_check
ROOT="$repo" "$repo/scripts/check-qwen36-xpu-xccl-health.sh" >"$o/postflight-compute-xccl.txt" 2>&1
log "=== r307 regression chain complete ==="; echo done > ${R}/r307-regression-DONE
