#!/usr/bin/env bash
# Stock vLLM XPU v0.29.0 (vllm/vllm-openai-xpu@96db42e2, V1 runner pinned, no lab overlays) on card 1: no-spec oracle for
# the L=14 prompt (token dump), then depth 3: the boundary tail reproducer against that oracle, and the sequential
# boundary probe (L=8..27) against a stock no-spec boundary oracle. Attributes the defect upstream or not.
set -uo pipefail
out=/mnt/fast-ai/bench-results/rebase-v0290-20260912/stock-boundary; repo=/home/steve/b70-optimization-lab; img=vllm/vllm-openai-xpu:latest; port=18185
log(){ echo "[stock $(date +%T)] $*" | tee -a $out/campaign.log; }
docker image inspect $img --format '{{.Id}} {{.RepoDigests}}' > $out/image.txt
serve(){ local arm=$1 spec=$2; local name=stock-boundary-$arm; mkdir -p $out/$arm-cache
  docker run -d --name $name --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
    -p 127.0.0.1:$port:8000 -v /home/steve/llm-models/qwen35-4b-w4a16:/model:ro -v $out/$arm-cache:/root/.cache/vllm \
    -e ZE_AFFINITY_MASK=1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_USE_V2_MODEL_RUNNER=0 -e SPEC="$spec" \
    --entrypoint bash $img -lc 'exec vllm serve /model --served-model-name m --host 0.0.0.0 --port 8000 --tensor-parallel-size 1 --dtype float16 --quantization compressed-tensors --gpu-memory-utilization 0.9 --max-model-len 256 --max-num-seqs 4 --no-enable-prefix-caching ${SPEC:+--speculative-config "$SPEC"}' >/dev/null
  log "$arm launched"; for i in $(seq 1 150); do curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && break; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 10; done
  curl -fsS http://127.0.0.1:$port/health >/dev/null 2>&1 && log "$arm healthy" || { log "$arm NOT healthy"; docker logs $name > $out/$arm.server.log 2>&1; docker rm -f $name >/dev/null 2>&1; return 1; }
}
stop(){ local name=stock-boundary-$1; docker logs $name > $out/$1.server.log 2>&1; docker stop -t 60 $name >/dev/null 2>&1; sleep 3; docker rm -f $name >/dev/null 2>&1; }
if serve mtp0 ""; then
  python3 $repo/experiments/qwen35-4b-b70/probes/max-len-divergence-probe.py --base http://127.0.0.1:$port --model m --len 14 --max-tokens 242 --iters 1 --out $out/mtp0-L14.json > $out/mtp0-L14.stdout 2>&1; log "mtp0 L14: $(tail -1 $out/mtp0-L14.stdout | cut -c1-120)"
  python3 $repo/experiments/qwen35-4b-b70/probes/max-len-boundary-probe.py --base http://127.0.0.1:$port --model m --max-model-len 256 --min-len 8 --max-len 27 --iters 2 --out $out/mtp0.json > $out/mtp0.stdout 2>&1; log "mtp0 boundary: $(tail -1 $out/mtp0.stdout | cut -c1-120)"
  stop mtp0
fi
if serve mtp3 '{"method":"qwen3_5_mtp","num_speculative_tokens":3}'; then
  python3 $repo/experiments/qwen35-4b-b70/probes/boundary-tail-probe.py --base http://127.0.0.1:$port --model m --oracle $out/mtp0-L14.json --out $out/mtp3-tail.json > $out/mtp3-tail.stdout 2>&1; log "mtp3 tail: $(grep SUMMARY $out/mtp3-tail.stdout | cut -c1-200)"
  python3 $repo/experiments/qwen35-4b-b70/probes/max-len-boundary-probe.py --base http://127.0.0.1:$port --model m --max-model-len 256 --min-len 8 --max-len 27 --iters 2 --oracle $out/mtp0.json --out $out/mtp3.json > $out/mtp3.stdout 2>&1; log "mtp3 boundary: $(tail -1 $out/mtp3.stdout | cut -c1-120)"
  python3 $repo/experiments/qwen35-4b-b70/probes/max-len-boundary-probe.py --base http://127.0.0.1:$port --model m --max-model-len 256 --min-len 8 --max-len 27 --iters 4 --concurrency 4 --oracle $out/mtp0.json --out $out/mtp3-c4.json > $out/mtp3-c4.stdout 2>&1; log "mtp3 boundary c4: $(tail -1 $out/mtp3-c4.stdout | cut -c1-120)"
  stop mtp3
fi
log "=== stock boundary complete ==="; echo done > $out/DONE
