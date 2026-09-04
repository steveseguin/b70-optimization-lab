#!/usr/bin/env bash
# R192 (2026-09-03): does the MTP depth-2 phantom first token reproduce on the STOCK upstream vLLM XPU image the lane
# was built from (vllm/vllm-openai-xpu@sha256:f01e24f6..., no lab patches)? Two servers: default (async scheduling on)
# and --no-async-scheduling; the same 64-prompt sequential pass; compare first tokens row by row. Waits for pid $1.
set -uo pipefail
while kill -0 "${1:?pid}" 2>/dev/null; do sleep 30; done
repo=/home/steve/b70-optimization-lab; out=/mnt/fast-ai/bench-results/qwen38-stock-f01e-mtp2-phantom-20260903-r192; mkdir -p "$out"
img=vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f
model=/mnt/fast-ai/llm-models/qwen3.8-27b-fp8; suite=$repo/experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json; port=18129
cat /proc/sys/kernel/random/boot_id >"$out/boot-id.txt"; docker image inspect "$img" --format '{{.Id}}' >"$out/image-id.txt"
for arm in async-on async-off; do
  extra=""; [[ $arm == async-off ]] && extra="--no-async-scheduling"
  name=qwen38-stock-r192-$arm; cache=$out/$arm-cache; mkdir -p "$cache" "$out/$arm"
  docker run -d --rm --name "$name" --ulimit core=0 --memory 12g --memory-swap 16g --device /dev/dri:/dev/dri --group-add render --cap-add SYS_PTRACE --security-opt label=disable --ipc=host --shm-size=8g \
    -p 127.0.0.1:$port:8000 -v "$model:/model:ro" -v "$cache:/root/.cache/vllm" \
    -e ZE_AFFINITY_MASK=0,1 -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1 -e VLLM_TARGET_DEVICE=xpu -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
    -e PYTORCH_ALLOC_CONF=expandable_segments:True -e CCL_ATL_TRANSPORT=ofi -e FI_PROVIDER=tcp -e FI_TCP_IFACE=lo -e CCL_ZE_IPC_EXCHANGE=pidfd -e CCL_SEND=direct -e CCL_RECV=direct \
    -e CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296 -e CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296 \
    --entrypoint bash "$img" -lc "exec vllm serve /model --served-model-name stock-mtp2 --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --dtype float16 --quantization fp8 --kv-cache-dtype auto --gpu-memory-utilization 0.95 --max-model-len 256 --block-size 64 --max-num-seqs 64 --max-num-batched-tokens 512 --no-enable-prefix-caching --enable-prompt-tokens-details --language-model-only --speculative-config '{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":2}' $extra" >"$out/$arm/docker-run.stdout" 2>&1
  echo "[r192 $(date +%T)] $arm launched" | tee -a "$out/campaign.log"
  deadline=$(( $(date +%s) + 2700 )); ok=0
  while (( $(date +%s) < deadline )); do curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1 && { ok=1; break; }; docker ps --format '{{.Names}}' | grep -q "^$name$" || break; sleep 15; done
  docker logs "$name" >"$out/$arm/server.log" 2>&1 || true
  if (( ok )); then
    echo "[r192 $(date +%T)] $arm healthy" | tee -a "$out/campaign.log"
    python3 "$repo/scripts/bench-openai-concurrency-oracle.py" --base-url "http://127.0.0.1:$port" --model stock-mtp2 --api-mode completions --suite "$suite" --concurrency 64 --repeats 1 --max-tokens 128 --seed 42 --timeout 600 \
      --request-extra-json '{"ignore_eos":true,"temperature":0}' --return-token-ids --out "$out/$arm/ladder-c1.json" >"$out/$arm/harness.stdout" 2>&1; echo "[r192 $(date +%T)] $arm harness exit $?" | tee -a "$out/campaign.log"
  else echo "[r192 $(date +%T)] ABORT: $arm server did not become healthy" | tee -a "$out/campaign.log"; fi
  docker logs "$name" >"$out/$arm/server.log" 2>&1 || true; docker stop -t 120 "$name" >/dev/null 2>&1 || true; sleep 5
done
python3 - "$out" <<'PY'
import json,sys,os
out=sys.argv[1]; res={"kind":"stock-f01e-mtp2-phantom","image_id":open(f"{out}/image-id.txt").read().strip()}
try:
    a={r["prompt_id"]:r["token_ids"] for r in json.load(open(f"{out}/async-on/ladder-c1.json"))["oracle"]["rows"]}
    b={r["prompt_id"]:r["token_ids"] for r in json.load(open(f"{out}/async-off/ladder-c1.json"))["oracle"]["rows"]}
    res["n_rows"]=len(a); res["first_token_differs"]=[(k,a[k][:3],b[k][:3]) for k in a if a[k][0]!=b[k][0]]
    res["rows_differing_anywhere"]=[(k,next((i for i in range(min(len(a[k]),len(b[k]))) if a[k][i]!=b[k][i]),None)) for k in a if a[k]!=b[k]]
except Exception as e: res["error"]=repr(e)
json.dump(res,open(f"{out}/result.json","w"),indent=1); print("[r192] RESULT", json.dumps(res)[:600])
PY
echo "[r192 $(date +%T)] campaign complete" | tee -a "$out/campaign.log"
