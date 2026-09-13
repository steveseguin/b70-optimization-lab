#!/usr/bin/env bash
# FP8 27B lane, short-prompt harness (bosd's, lab pool), TP2 depth 1 (alias k=2), 30 repeats: the R187 profile on the
# R156 lineage image vs R304. Queued behind the high-concurrency chain (both cards).
set -uo pipefail
repo=/home/steve/b70-optimization-lab; out=/mnt/fast-ai/bench-results/rebase-v0290-20260912/alias-fp8; mkdir -p $out
wrap=$out/campaign.log; log(){ echo "[alias-fp8 $(date +%T)] $*" | tee -a $wrap; }
until [[ -e /mnt/fast-ai/bench-results/rebase-v0290-highconc-20260913-DONE ]]; do sleep 30; done
while docker ps --format '{{.Names}}' | grep -qE 'qwen3[58]|rebase-|upstream-'; do sleep 20; done; sleep 10
arm(){ local arm=$1 image=$2 khead=$3; local port=18164 name=qwen38-fp8-alias-$arm; local id; id=$(docker image inspect $image --format '{{.Id}}')
  ( IMAGE=$image EXPECTED_IMAGE_ID=$id EXPECTED_KERNEL_HEAD=$khead SKIP_IMAGE_CONTRACT=$4 VLLM_USE_V2_MODEL_RUNNER=0 MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-fp8 PORT=$port CONTAINER_NAME=$name SERVED_MODEL_NAME=m VLLM_CACHE_DIR=$out/$arm-cache \
    bash $repo/experiments/qwen38-27b-b70/scripts/run-20260903-qwen38-fp8-mtp1-whole-graph-r187-server.sh > $out/$arm.launcher.log 2>&1 ) &
  log "$arm launched ($image)"; local ok=0; for i in $(seq 1 150); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && { ok=1; break; }; sleep 10; done
  if (( ok )); then log "$arm healthy"; python3 $repo/experiments/qwen35-4b-b70/probes/alias-harness-lab.py --base http://127.0.0.1:$port/v1 --model m --spec-tokens 1 --iters 30 --tag $arm > $out/$arm.harness.stdout 2>&1; log "$arm harness exit $?"; grep -E '^(ALIAS|control)' $out/$arm.harness.stdout | cut -c1-120 | sed 's/^/    /' | tee -a $wrap
  else log "$arm did NOT become healthy"; tail -3 $out/$arm.launcher.log | cut -c1-160 | tee -a $wrap; fi
  docker logs $name > $out/$arm.server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 5; docker rm -f $name >/dev/null 2>&1
}
arm r304 neural-download/vllm-openai-xpu:qwen38-int4-v0290-rebase-r304 6d92b1bfbf32767ecda8e819613eb151e70030ad 0
r156=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -m1 'qwen38-fp8-mtp1-gdn-split-mixed-r156$' || true)
[[ -n "$r156" ]] && arm r156 "$r156" 1e90ffa672ba02f17a909da11838a4c55b199783 0 || log "R156 image not local; old-image arm skipped"
log "=== fp8 short-prompt chain complete ==="; echo done > $out/DONE
