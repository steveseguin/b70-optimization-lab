#!/usr/bin/env bash
# Usage: run-arm.sh <control|candidate>
set -uo pipefail
ARM=${1:?arm}
PAD=0; [[ "$ARM" == candidate ]] && PAD=32
RUN=/mnt/fast-ai/bench-results/qwen38-fp8-tp2-mtp1-w8a16-decode-pad-rows-20260902-r118
NAME=qwen38-fp8-mtp1-w8a16-decode-pad-rows-r118-$ARM
mkdir -p "$RUN/cache-$ARM"
cd /home/steve/b70-optimization-lab
date -Is > "$RUN/$ARM-start-time.txt"
env MODEL_DIR=/mnt/fast-ai/llm-models/qwen3.8-27b-fp8 VLLM_CACHE_DIR="$RUN/cache-$ARM" \
  IMAGE=neural-download/vllm-openai-xpu:qwen38-fp8-mtp1-w8a16-decode-pad-rows-r118 \
  EXPECTED_IMAGE_ID=sha256:95742ce8493671fb28b0b53db77a2f0c240e8d82355f20b756ab2479d037b8d0 \
  CONTAINER_NAME="$NAME" PORT=18129 SERVED_MODEL_NAME=qwen38-fp8-mtp1-r118 \
  VLLM_XPU_W8A16_DECODE_PAD_ROWS=$PAD \
  VLLM_XPU_GDN_ISOLATE_PROJECTION_PREFILL_REQUESTS=0 VLLM_XPU_GDN_PROJECTION_TRACE_FILE= \
  nohup experiments/qwen38-27b-b70/scripts/run-20260902-qwen38-fp8-mtp1-gdn-r99-all-phases-r117-server.sh > "$RUN/$ARM-server.log" 2>&1 &
for i in $(seq 1 150); do
  curl -sf http://127.0.0.1:18129/v1/models >/dev/null 2>&1 && { echo "$ARM READY after ${i}x5s"; break; }
  grep -q Traceback "$RUN/$ARM-server.log" && { echo "$ARM TRACEBACK"; exit 1; }
  sleep 5
done
curl -sf http://127.0.0.1:18129/v1/models >/dev/null || { echo "$ARM not ready"; exit 2; }
# one warm pass (JIT), then the measured pass
python3 scripts/bench-openai-concurrency-oracle.py --base-url http://127.0.0.1:18129 --model qwen38-fp8-mtp1-r118 --api-mode completions \
  --suite experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json --concurrency 1 --repeats 1 --max-tokens 128 --seed 42 \
  --request-extra-json '{"cache_prompt": false, "ignore_eos": true, "temperature": 0}' --return-token-ids --out "$RUN/$ARM-warm.json" > "$RUN/$ARM-warm.stdout" 2>&1
python3 scripts/bench-openai-concurrency-oracle.py --base-url http://127.0.0.1:18129 --model qwen38-fp8-mtp1-r118 --api-mode completions \
  --suite experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp2-http-smallctx-suite.json --concurrency 1,2 --repeats 5 --max-tokens 128 --seed 42 \
  --request-extra-json '{"cache_prompt": false, "ignore_eos": true, "temperature": 0}' --return-token-ids --out "$RUN/$ARM-measured.json" > "$RUN/$ARM-measured.stdout" 2>&1
echo "$ARM measured exit=$?"
grep -c 'R118\|xpu_w8a16_padded' "$RUN/$ARM-server.log" || true
date -Is > "$RUN/$ARM-stop-time.txt"
docker stop "$NAME" >/dev/null 2>&1; sleep 3
xpu-smi discovery > "$RUN/$ARM-xpu-after.txt" 2>&1; grep -c 'Device State: normal' "$RUN/$ARM-xpu-after.txt"
