#!/usr/bin/env bash
# Stock v0.29.0 single-user baselines for the rebase decision: 4B and 9B W4A16, depth-3 MTP and no-spec, one card
# (index 0), same harness/suite shape as the lab's strict pairs (c1, 64 prompts, 128 tokens, greedy).
set -uo pipefail
img=${IMG:-vllm/vllm-openai-xpu:latest}; tag=${TAG:-v0.29.0}; out=/mnt/fast-ai/bench-results/rebase-v0290-20260912/stock-$tag; mkdir -p $out
suite=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json; port=18150
log(){ echo "[$tag $(date +%T)] $*" | tee -a $out/campaign.log; }
docker image inspect $img --format '{{.Id}}' > $out/image-id.txt
for lane in 4b 9b; do model=/home/steve/llm-models/qwen35-$lane-w4a16
 for arm in mtp3 mtp0; do
  specjson=""; [[ $arm == mtp3 ]] && specjson='{"method":"qwen3_5_mtp","num_speculative_tokens":3}'
  name=rebase-stock-$tag-$lane-$arm; mkdir -p $out/$lane-$arm-cache
  docker run -d --name $name --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
    -p 127.0.0.1:$port:8000 -v $model:/model:ro -v $out/$lane-$arm-cache:/root/.cache/vllm \
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e SPEC="$specjson" \
    --entrypoint bash $img -lc "exec vllm serve /model --served-model-name m --host 0.0.0.0 --port 8000 --tensor-parallel-size 1 --dtype float16 --quantization compressed-tensors --gpu-memory-utilization 0.9 --max-model-len 4096 --max-num-seqs 64 --no-enable-prefix-caching \${SPEC:+--speculative-config \"\$SPEC\"}" >/dev/null
  log "$lane $arm launched"; ( docker logs -f $name > $out/$lane-$arm.server.live.log 2>&1 ) &
  deadline=$(( $(date +%s)+1500 )); ok=0
  while (( $(date +%s) < deadline )); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 10; done
  if (( ok )); then log "$lane $arm healthy"
    python3 /home/steve/b70-optimization-lab/scripts/bench-openai-concurrency-oracle.py --base-url http://127.0.0.1:$port --model m --api-mode completions --suite $suite --concurrency 1,8,64 --repeats 2 --max-tokens 128 --seed 42 --timeout 900 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --out $out/$lane-$arm.ladder.json > $out/$lane-$arm.harness.stdout 2>&1; log "$lane $arm harness exit $?"
    python3 - $out/$lane-$arm.ladder.json <<'PY' | tee -a $out/campaign.log
import json,sys; d=json.load(open(sys.argv[1]))
print('  ', [(b['concurrency'],b['repeat'],round(b['aggregate_tok_s_wall'],1),f"{b['oracle_exact_count']}/{b['oracle_exact_total']}") for b in d['batches']])
PY
  else log "$lane $arm did NOT become healthy"; fi
  docker stop -t 60 $name >/dev/null 2>&1; sleep 3; docker logs $name > $out/$lane-$arm.server.log 2>&1; docker rm -f $name >/dev/null 2>&1
 done; done
log "=== done ==="
