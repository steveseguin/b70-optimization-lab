#!/usr/bin/env bash
# Qwen3.6 27B / 35B A3B INT4 (sym_int4, in-place) — ONE Arc B70 GPU, b2 image
#
# 2026-08-04 recipe. Verified on 2x Intel Arc B70 (Battlemage G31), xe driver,
# intel/llm-scaler-vllm:0.21.0-b2.
#
# Why this path (all alternatives failed on this hardware — see README):
#   - b2's multi-GPU all-reduce is broken on B70: Intel's own source admits it
#     returns NaN on prefill-sized buffers ("cascades to garbage ('!!!!') decode
#     output"). TP=1 avoids the collective entirely.
#   - sym_int4 is b2's native online INT4 method (GPTQ-layout fast path,
#     group_size=128, symmetric). BF16 -> RAM offload -> INT4 in place via
#     VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1, so VRAM never holds full BF16.
#   - --kv-cache-dtype fp8_e4m3 engages the Triton attention backend's FP8 KV
#     path (flash-attn fp8 is compiled out on XPU: flash_attn_supports_fp8=False).
#     ~3x KV tokens vs fp16 at the same memory.
#   - MTP speculative decoding verified: ~85-88% draft acceptance.
#   - Vision verified (sym_int4 auto-skips the vision tower).
#
# Set GPU_ID=0 for the 27B, GPU_ID=1 for the 35B (one model per GPU).
# NOTE: use ZE_AFFINITY_MASK only — ONEAPI_DEVICE_SELECTOR=level_zero:1 breaks
# device discovery on the second GPU (torch sees zero devices).
#
set -euo pipefail

# ──────────────────────────────────────────────
# Abstracted top-level variables
# ──────────────────────────────────────────────
IMAGE="intel/llm-scaler-vllm:0.21.0-b2"
# Pick the model: 27B dense or 35B A3B MoE (BF16 source checkpoint).
MODEL_HOST_DIR="/home/dom/llm-scaler-prod/models/Qwen3.6-27B"   # or Qwen3.6-35B-A3B
MODEL="/model"
SERVED_NAME="qwen36-27b"        # or qwen36-35b
NAME="vllm-qwen36-27b-int4"     # unique container name per instance
PORT=8001                       # 8002 for the second instance
GPU_ID="${GPU_ID:-0}"           # 0 -> 27B, 1 -> 35B
MAX_LEN="${MAX_LEN:-131072}"    # FINAL: 27B=131072 (131k), 35B=262144 (262k)
GPU_UTIL="${GPU_UTIL:-0.95}"    # fp8 KV fits full 262144 at 0.95 (needs ~9.1 GiB)
MAX_SEQS="${MAX_SEQS:-2}"       # FINAL: 27B=2, 35B=3
# ──────────────────────────────────────────────

# FINAL sampling (A/B-verified 2026-08-05):
#   27B: temp 0.6, presence_penalty 0.0  |  35B: temp 1.0, presence_penalty 1.5
# MTP is DISABLED (default) — A/B showed MTP costs 3.45x (35B) / 1.56x (27B)
# decode throughput at depth 32768. See benchmarks/BENCHMARKS.md.
OVERRIDE_GEN='{"temperature":0.6,"top_p":0.95,"top_k":20,"min_p":0.0,"presence_penalty":0.0,"repetition_penalty":1.0}'
CHAT_TMPL='{"enable_thinking":true,"preserve_thinking":true}'

test -s "${MODEL_HOST_DIR}/config.json" || { echo "ERROR: model dir incomplete: ${MODEL_HOST_DIR}" >&2; exit 2; }

# ──────────────────────────────────────────────
# Write the in-container launch script (avoids nested-quote JSON mangling
# through docker -lc "..."; the JSON args are not shell-safe single-quoted)
# ──────────────────────────────────────────────
LAUNCH_SH="/tmp/int4-serve-${NAME}.sh"
cat > "${LAUNCH_SH}" <<EOF
#!/usr/bin/env bash
exec vllm serve ${MODEL} \\
  --served-model-name ${SERVED_NAME} \\
  --host 0.0.0.0 --port ${PORT} \\
  --tensor-parallel-size 1 \\
  --dtype float16 --quantization sym_int4 \\
  --max-model-len ${MAX_LEN} --gpu-memory-utilization ${GPU_UTIL} \\
  --max-num-seqs ${MAX_SEQS} --max-num-batched-tokens 4096 \\
  --kv-cache-dtype fp8_e4m3 \\
  --enable-auto-tool-choice --tool-call-parser qwen3_xml \\
  --reasoning-parser qwen3 \\
  --override-generation-config '${OVERRIDE_GEN}' \\
  --default-chat-template-kwargs '${CHAT_TMPL}' \\
  --trust-remote-code --enforce-eager
EOF
chmod +x "${LAUNCH_SH}"

# ──────────────────────────────────────────────
# Cleanup stale container
# ──────────────────────────────────────────────
echo "=== Cleaning up stale ${NAME} ==="
if [ "$(docker ps -a -q -f name=^/${NAME}$)" ]; then
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
fi

# ──────────────────────────────────────────────
# Launch (ZE_AFFINITY_MASK only; see header note on GPU 1)
# ──────────────────────────────────────────────
echo ""
echo "=== Starting ${SERVED_NAME} (BF16 -> sym_int4, fp8 KV, MTP) on GPU ${GPU_ID} ==="
echo "  Model: ${MODEL_HOST_DIR}"
echo "  Port: ${PORT}  |  Context: ${MAX_LEN}  |  Max Seqs: ${MAX_SEQS}"
echo ""

docker run -d \
  --name "${NAME}" \
  --restart unless-stopped \
  --privileged \
  --net=host \
  --ipc=host \
  --shm-size=32g \
  --device=/dev/dri \
  --group-add "$(getent group render | cut -d: -f3)" \
  -v "${MODEL_HOST_DIR}":/model:ro \
  -v "${LAUNCH_SH}":/serve.sh:ro \
  -e ZE_AFFINITY_MASK="${GPU_ID}" \
  -e VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1 \
  -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
  -e VLLM_XPU_ENABLE_XPU_GRAPH=0 \
  -e VLLM_XPU_USE_SAMPLER_KERNEL=0 \
  -e PYTORCH_ALLOC_CONF="expandable_segments:True" \
  -e UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1 \
  --entrypoint /bin/bash \
  "${IMAGE}" /serve.sh

# ──────────────────────────────────────────────
# Health check loop (INT4 quant + MTP load ~4 min)
# ──────────────────────────────────────────────
echo ""
echo "=== Monitoring engine startup ==="
START_TIME=$(date +%s)
IS_HEALTHY=false

for _ in $(seq 1 90); do
  if [ "$(docker inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)" != "true" ]; then
    echo -e "\nCRITICAL: Engine process crashed on startup!"
    docker logs "${NAME}" --tail 40
    exit 1
  fi

  if curl -fsS -m2 "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    IS_HEALTHY=true
    echo -e "\nEngine online after $(( $(date +%s) - START_TIME ))s"
    break
  fi

  echo "  [$(( $(date +%s) - START_TIME ))s] still loading..."
  docker logs "${NAME}" --tail 1
  sleep 10
done

if [ "$IS_HEALTHY" != "true" ]; then
  echo ""
  echo "ERROR: ${NAME} hung or did not become healthy within the timeout window."
  docker logs "${NAME}" --tail 40
  exit 1
fi

echo ""
echo "========================================"
echo " ENGINE ONLINE"
echo "========================================"
echo " Endpoint: http://localhost:${PORT}/v1/chat/completions"
echo ""

# ──────────────────────────────────────────────
# Smoke tests
# ──────────────────────────────────────────────
echo "=== KV cache ==="
docker logs "${NAME}" 2>&1 | grep -aiE 'KV cache size|Available KV|Model loading took' | tail -3

echo ""
echo "=== Smoke test: thinking ==="
curl -s -H "Content-Type: application/json" http://localhost:${PORT}/v1/chat/completions \
  -d '{"model":"'"${SERVED_NAME}"'","messages":[{"role":"user","content":"Name three primary colors."}],"max_tokens":60}' \
  | python3 -m json.tool 2>/dev/null \
  || echo "smoke request failed (server may still be warming)"

echo ""
echo "=== Smoke test: tool call (auto choice) ==="
curl -s -H "Content-Type: application/json" http://localhost:${PORT}/v1/chat/completions \
  -d '{"model":"'"${SERVED_NAME}"'","tool_choice":"auto","max_tokens":300,
       "tools":[{"type":"function","function":{"name":"get_weather","description":"Get weather for a city","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],
       "messages":[{"role":"user","content":"Weather in Knoxville?"}]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); m=d['choices'][0]['message']; print('tool_calls:', json.dumps(m.get('tool_calls'))[:250]); print('finish:', d['choices'][0]['finish_reason'])" 2>/dev/null \
  || echo "tool smoke failed (server may still be warming)"

echo ""
echo "=== Done ==="