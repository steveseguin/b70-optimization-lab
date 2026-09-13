#!/usr/bin/env bash
# Short-prompt harness (bosd's, lab pool) on the remaining lanes on R304: 9B W4A16 one card depth 3 (alias k=4), then
# 27B INT4 TP2 depth 4 (alias k=5). 30 greedy repeats per prompt length; expected 0/30 everywhere.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; out=/mnt/fast-ai/bench-results/rebase-v0290-20260912/alias-9b-27b; mkdir -p $out
wrap=$out/campaign.log; log(){ echo "[alias-9b27b $(date +%T)] $*" | tee -a $wrap; }
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 20; done; sleep 5
img=neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304; id=$(docker image inspect $img --format '{{.Id}}'); kh=6d92b1bfbf32767ecda8e819613eb151e70030ad
run(){ local arm=$1 launcher=$2 depth=$3 port=$4; shift 4; local name=rebase-alias4-$arm
  ( env IMAGE=$img EXPECTED_IMAGE_ID=$id EXPECTED_KERNEL_HEAD=$kh VLLM_USE_V2_MODEL_RUNNER=0 PORT=$port CONTAINER_NAME=$name SERVED_MODEL_NAME=m VLLM_CACHE_DIR=$out/$arm-cache MTP_DEPTH=$depth "$@" bash $launcher > $out/$arm.launcher.log 2>&1 ) &
  log "$arm launched"; local ok=0; for i in $(seq 1 150); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && { ok=1; break; }; sleep 10; done
  if (( ok )); then log "$arm healthy"; python3 $repo/experiments/qwen35-4b-b70/probes/alias-harness-lab.py --base http://127.0.0.1:$port/v1 --model m --spec-tokens $depth --iters 30 --tag $arm > $out/$arm.harness.stdout 2>&1; log "$arm harness exit $?"; grep -E '^(ALIAS|control|!!)' $out/$arm.harness.stdout | cut -c1-120 | sed 's/^/    /' | tee -a $wrap
  else log "$arm did NOT become healthy"; tail -3 $out/$arm.launcher.log | cut -c1-160 | tee -a $wrap; fi
  docker logs $name > $out/$arm.server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 5; docker rm -f $name >/dev/null 2>&1
}
run 9b $repo/repro/qwen35-9b-w4a16-b70/scripts/run-qwen35-9b-w4a16-server.sh 3 18165 MODEL_DIR=/home/steve/llm-models/qwen35-9b-w4a16 TENSOR_PARALLEL_SIZE=1
run 27b-int4 $repo/repro/qwen38-27b-autoround-int4-b70/scripts/run-fixed-k-mtp-server.sh 4 18166 MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-gptq-relabel
log "=== short-prompt 9B/27B chain complete ==="; echo done > $out/DONE
