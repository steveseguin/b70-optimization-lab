#!/usr/bin/env bash
# Upstream reproduction (2026-09-12) of the historical MTP depth-2 "phantom first token" (R192/R194, 2026-09-03: 3 of 6
# stock servers on vllm/vllm-openai-xpu@f01e24f6 began one request's output with the prompt's last token). Same model,
# prompts, harness and server shape on the image IMG=<image>; arms as R192/R194: compiled async-on, compiled
# --no-async-scheduling, --enforce-eager async-on (x2). Detector: any oracle row whose first token != the row's normal
# first token (the R192 result JSON lists the expected heads) and, for every row, the R192/R194 token arrays for diff.
set -uo pipefail
img=${IMG:?}; tag=${TAG:?}; out=/mnt/fast-ai/bench-results/upstream-repro-20260912/phantom-$tag; mkdir -p "$out"
model=/mnt/fast-ai/llm-models/qwen3.8-27b-fp8; suite=/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json; port=18141
log() { echo "[$tag $(date +%T)] $*" | tee -a "$out/campaign.log"; }
docker image inspect "$img" --format '{{.Id}}' >"$out/image-id.txt"; cat /proc/sys/kernel/random/boot_id >"$out/boot-id.txt"
for arm in compiled-async-on compiled-async-off eager-async-on-1 eager-async-on-2; do
  extra=""; [[ $arm == compiled-async-off ]] && extra="--no-async-scheduling"; [[ $arm == eager-* ]] && extra="--enforce-eager"
  name=upstream-phantom-$tag-$arm; mkdir -p "$out/$arm" "$out/$arm-cache"
  docker run -d --name "$name" --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
    -p 127.0.0.1:$port:8000 -v "$model:/model:ro" -v "$out/$arm-cache:/root/.cache/vllm" \
    -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
    -e PYTORCH_ALLOC_CONF=expandable_segments:True -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct \
    -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    --entrypoint bash "$img" -lc "exec vllm serve /model --served-model-name stock-mtp2 --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.95 --max-model-len 256 --block-size 64 --max-num-seqs 64 --max-num-batched-tokens 512 --no-enable-prefix-caching --speculative-config '{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":2}' $extra" >/dev/null
  log "$arm launched"; ( docker logs -f "$name" >"$out/$arm/server.live.log" 2>&1 ) &
  deadline=$(( $(date +%s) + 2700 )); ok=0
  while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 15; done
  if (( ok )); then
    log "$arm healthy"
    python3 /home/steve/b70-optimization-lab/scripts/bench-openai-concurrency-oracle.py --base-url "http://127.0.0.1:$port" --model stock-mtp2 --api-mode completions --suite "$suite" --concurrency 64 --repeats 1 --max-tokens 128 --seed 42 --timeout 600 --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --out "$out/$arm/ladder-c1.json" >"$out/$arm/harness.stdout" 2>&1; log "$arm harness exit $?"
    python3 - "$out/$arm/ladder-c1.json" <<'PY' | tee -a "$out/campaign.log"
import json,sys
d=json.load(open(sys.argv[1])); rows=d['oracle']['rows']
heads={}
for r in rows: heads.setdefault(r['prompt_id'].split('-c')[0],[]).append((r['prompt_id'],r['token_ids'][:3]))
odd=[]
for base,lst in heads.items():
    from collections import Counter
    c=Counter(tuple(t[:1]) for _,t in lst); common=c.most_common(1)[0][0]
    odd+=[(pid,t) for pid,t in lst if tuple(t[:1])!=common]
print("first-token outliers:", odd if odd else "none", "| rows", len(rows))
PY
  else log "$arm did NOT become healthy"; fi
  docker stop -t 120 "$name" >/dev/null 2>&1 || true; sleep 5; docker logs "$name" >"$out/$arm/server.log" 2>&1 || true; docker rm -f "$name" >/dev/null 2>&1 || true
done
log "=== done ==="
