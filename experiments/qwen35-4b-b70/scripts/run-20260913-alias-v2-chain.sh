#!/usr/bin/env bash
# Alias / one-token prefill test, round 2 (2026-09-13): lab harness (larger pool, every k in 1..alias+2), 30 greedy repeats,
# 4B one card. Arms: r302 (guard only) / r303 (guard + #51565 first-chunk fix) / r294b (served) / r303 without speculation
# (does the one-token failure need MTP?). Queued behind the first alias chain.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; R=/mnt/fast-ai/bench-results/rebase-v0290-20260912; out=$R/alias-v2; mkdir -p $out
wrap=$out/campaign.log; log(){ echo "[alias2 $(date +%T)] $*" | tee -a $wrap; }
until [[ -e $R/alias-DONE ]]; do sleep 20; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-'; do sleep 20; done; sleep 10
arm(){ local arm=$1 image=$2 khead=$3 depth=$4; local port=18162 name=rebase-alias2-$arm
  local id; id=$(docker image inspect $image --format '{{.Id}}'); echo "$image $id" > $out/$arm.image.txt
  ( IMAGE=$image EXPECTED_IMAGE_ID=$id EXPECTED_KERNEL_HEAD=$khead SKIP_IMAGE_CONTRACT=1 VLLM_USE_V2_MODEL_RUNNER=0 MODEL_DIR=/home/steve/llm-models/qwen35-4b-w4a16 \
    PORT=$port CONTAINER_NAME=$name SERVED_MODEL_NAME=m VLLM_CACHE_DIR=$out/$arm-cache MTP_DEPTH=$depth TENSOR_PARALLEL_SIZE=1 \
    bash $repo/repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh > $out/$arm.launcher.log 2>&1 ) &
  log "$arm launched ($image depth $depth)"; local deadline=$(( $(date +%s)+1500 )) ok=0
  while (( $(date +%s) < deadline )); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && { ok=1; break; }; sleep 10; done
  if (( ok )); then log "$arm healthy"
    python3 $repo/experiments/qwen35-4b-b70/probes/alias-harness-lab.py --base http://127.0.0.1:$port/v1 --model m --spec-tokens $depth --iters 30 --tag $arm > $out/$arm.harness.stdout 2>&1; log "$arm harness exit $?"
    grep -E '^(ALIAS|control|!!)' $out/$arm.harness.stdout | cut -c1-120 | sed 's/^/    /' | tee -a $wrap
  else log "$arm did NOT become healthy"; fi
  docker logs $name > $out/$arm.server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 5; docker rm -f $name >/dev/null 2>&1
}
arm r302 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r302 6d92b1bfbf32767ecda8e819613eb151e70030ad 3
arm r303 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r303 6d92b1bfbf32767ecda8e819613eb151e70030ad 3
arm r294b neural-download/vllm-openai-xpu:qwen38-int4-draft-head-shortlist-r294b 1e90ffa672ba02f17a909da11838a4c55b199783 3
arm r303-mtp0 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r303 6d92b1bfbf32767ecda8e819613eb151e70030ad 0
arm r302-mtp0 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r302 6d92b1bfbf32767ecda8e819613eb151e70030ad 0
log "=== alias v2 complete ==="; echo done > $R/alias-v2-DONE
