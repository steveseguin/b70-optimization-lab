#!/usr/bin/env bash
# Uniform-decode shape-alias (vLLM #53051, guard PR #53059; bosd PR #47 harness) on the lab's 4B lane, one card, served
# configuration (depth 3 -> alias prompt length 4), 30 greedy repeats per prompt shape, four arms:
#   r301 (v0.29.0 rebase, no guard) / r302 (= r301 + guard) / r294b (served) / r294b + guard.
# Queued behind the 27B rb2 strict chain (both cards). Harness: probes/alias-harness-bosd.py (unmodified copy).
set -uo pipefail
repo=/home/steve/b70-optimization-lab; R=/mnt/fast-ai/bench-results/rebase-v0290-20260912; out=$R/alias; mkdir -p $out
wrap=$out/campaign.log; log(){ echo "[alias $(date +%T)] $*" | tee -a $wrap; }
until grep -q 'rb2: engine exit' /mnt/fast-ai/bench-results/qwen38-int4-rebase-v0290-20260912-wrapper.log 2>/dev/null; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 20; done; sleep 10
arm(){ local arm=$1 image=$2 khead=$3 v2=$4; local port=18161 name=rebase-alias-$arm
  local id; id=$(docker image inspect $image --format '{{.Id}}'); echo "$image $id" > $out/$arm.image.txt
  ( IMAGE=$image EXPECTED_IMAGE_ID=$id EXPECTED_KERNEL_HEAD=$khead SKIP_IMAGE_CONTRACT=1 VLLM_USE_V2_MODEL_RUNNER=$v2 MODEL_DIR=/home/steve/llm-models/qwen35-4b-w4a16 \
    PORT=$port CONTAINER_NAME=$name SERVED_MODEL_NAME=m VLLM_CACHE_DIR=$out/$arm-cache MTP_DEPTH=3 TENSOR_PARALLEL_SIZE=1 \
    bash $repo/repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh > $out/$arm.launcher.log 2>&1 ) &
  log "$arm launched ($image)"; local deadline=$(( $(date +%s)+1500 )) ok=0
  while (( $(date +%s) < deadline )); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && { ok=1; break; }; sleep 10; done
  if (( ok )); then log "$arm healthy"
    python3 $repo/experiments/qwen35-4b-b70/probes/alias-harness-bosd.py --base http://127.0.0.1:$port/v1 --model m --spec-tokens 3 --iters 30 --tag $arm > $out/$arm.harness.stdout 2>&1; log "$arm harness exit $?"
    grep -E '^(ALIAS|control)' $out/$arm.harness.stdout | cut -c1-140 | sed 's/^/    /' | tee -a $wrap
  else log "$arm did NOT become healthy"; fi
  docker logs $name > $out/$arm.server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 5; docker rm -f $name >/dev/null 2>&1
}
arm r301 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r301 6d92b1bfbf32767ecda8e819613eb151e70030ad 0
arm r302 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r302 6d92b1bfbf32767ecda8e819613eb151e70030ad 0
arm r294b neural-download/vllm-openai-xpu:qwen38-int4-draft-head-shortlist-r294b 1e90ffa672ba02f17a909da11838a4c55b199783 0
arm r294b-guard rebase/vllm-xpu:r294b-alias-guard 1e90ffa672ba02f17a909da11838a4c55b199783 0
log "=== alias chain complete ==="; echo done > $R/alias-DONE
