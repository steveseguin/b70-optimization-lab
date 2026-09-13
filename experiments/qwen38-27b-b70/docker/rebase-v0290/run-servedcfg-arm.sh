#!/usr/bin/env bash
# Rebase stage A comparison (2026-09-12): the lab's own 4B launcher chain (served configuration: depth 3, graph on,
# draft INT4 head + 67k shortlist, CLASSPAD=0, GDN spec group 16, gemma-rmsnorm packed serial exact ...) on
# (a) the stage-A image = stock v0.29.0 + ported Python overlays, stock 0.1.14.1 kernels; (b) the served R294b image.
# Same harness shape as the stock baseline (c1/8/64 x2, 128 tokens) so the three compare directly.
set -uo pipefail
repo=/home/steve/b70-optimization-lab; out=/mnt/fast-ai/bench-results/rebase-v0290-20260912/servedcfg; mkdir -p $out
suite=$repo/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json
log(){ echo "[servedcfg $(date +%T)] $*" | tee -a $out/campaign.log; }
run_arm(){ local arm=$1 image=$2 khead=$3; local port=18160 name=rebase-servedcfg-$arm
  local id; id=$(docker image inspect $image --format '{{.Id}}'); echo "$image $id" > $out/$arm.image.txt
  ( IMAGE=$image EXPECTED_IMAGE_ID=$id EXPECTED_KERNEL_HEAD=$khead SKIP_IMAGE_CONTRACT=1 MODEL_DIR=/home/steve/llm-models/qwen35-4b-w4a16 \
    PORT=$port CONTAINER_NAME=$name SERVED_MODEL_NAME=m VLLM_CACHE_DIR=$out/$arm-cache MTP_DEPTH=3 TENSOR_PARALLEL_SIZE=1 \
    bash $repo/repro/qwen35-4b-w4a16-b70/scripts/run-qwen35-4b-w4a16-server.sh > $out/$arm.launcher.log 2>&1 ) &
  log "$arm launched ($image)"
  local deadline=$(( $(date +%s)+1500 )) ok=0
  while (( $(date +%s) < deadline )); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && { ok=1; break; }; sleep 10; grep -q 'FAIL\|Error\|error' $out/$arm.launcher.log 2>/dev/null && ! docker ps --format '{{.Names}}' | grep -q "^$name$" && break; done
  if (( ok )); then log "$arm healthy"
    python3 $repo/scripts/bench-openai-concurrency-oracle.py --base-url http://127.0.0.1:$port --model m --api-mode completions --suite $suite --concurrency 1,8,64 --repeats 2 --max-tokens 128 --seed 42 --timeout 900 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --out $out/$arm.ladder.json > $out/$arm.harness.stdout 2>&1; log "$arm harness exit $?"
    python3 - $out/$arm.ladder.json <<'PY' | tee -a $out/campaign.log
import json,sys; d=json.load(open(sys.argv[1]))
print('  ', [(b['concurrency'],b['repeat'],round(b['aggregate_tok_s_wall'],1),f"{b['oracle_exact_count']}/{b['oracle_exact_total']}") for b in d['batches']])
PY
  else log "$arm did NOT become healthy"; tail -5 $out/$arm.launcher.log | cut -c1-200 | tee -a $out/campaign.log; fi
  docker logs $name > $out/$arm.server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 5; docker rm -f $name >/dev/null 2>&1
}



# usage: ARM=<name> IMG=<image> KHEAD=<kernel head sha> run-servedcfg-arm.sh
run_arm "${ARM:?}" "${IMG:?}" "${KHEAD:?}"
log "=== $ARM done ==="
