#!/usr/bin/env bash
# Qwen3.6 35B A3B FP8 (in-place quant) — TP=2 on both Arc B70 GPUs, thinking mode ON
#
# FRESH 2026-08-01 rebuild of the golden June recipe on intel/llm-scaler-vllm:0.21.0-b1
#
# Golden recipe (150 tok/s baseline, June):
#   - FULL BF16 checkpoint (NOT the pretrained FP8 — released 0.21 image lacks the
#     block-scaled XPU FP8 kernels; pretrained-FP8 falls back to BF16/slow/garbage)
#   - VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1  -> weights staged in system RAM, then
#     quantized to native per-tensor FP8 in place (no VRAM spike, correct scales)
#   - --dtype float16 --quantization fp8 (Intel XPU reference path)
#   - TP=2, both GPUs, port 8001
#
# Thinking: enabled via chat template kwargs + Qwen official non-greedy generation
# config (greedy breaks thinking mode).
#
set -euo pipefail

IMAGE="intel/llm-scaler-vllm:0.21.0-b1"
NAME="vllm-qwen36-35b-fp8"
MODEL_HOST_DIR="/home/dom/llm-scaler-prod/models/Qwen3.6-35B-A3B"
MODEL="/model"
SERVED_NAME="qwen36-35b-fp8"
PORT=8001
TP=2
MAX_LEN="${MAX_LEN:-262144}"
GPU_UTIL="${GPU_UTIL:-0.88}"
MAX_SEQS="${MAX_SEQS:-4}"
EAGER="${EAGER:-1}"
THINKING_BUDGET="${THINKING_BUDGET:-2048}"
# vLLM 0.21 applies this hard budget per request via thinking_token_budget.

# Qwen3.6 recommended general-thinking profile from the model card.
OVERRIDE_GEN='{"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0.0,"presence_penalty":1.5,"repetition_penalty":1.0}'
CHAT_TMPL='{"enable_thinking":true,"preserve_thinking":true}'
REASONING_CONFIG='{"reasoning_parser":"qwen3"}'
DOCKER_ARGS=(
  --restart unless-stopped
  --privileged
  --net=host
  --ipc=host
  --shm-size=32g
  --device=/dev/dri
  --group-add "$(getent group render | cut -d: -f3)"
  -v "${MODEL_HOST_DIR}":/model:ro
  -e ZE_AFFINITY_MASK=0,1
  -e ONEAPI_DEVICE_SELECTOR=level_zero:0,1
  -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn
  -e VLLM_OFFLOAD_WEIGHTS_BEFORE_QUANT=1
  -e PYTORCH_ALLOC_CONF="expandable_segments:True"
  -e TORCH_LLM_ALLREDUCE=1
  -e CCL_TOPO_P2P_ACCESS=1
  -e CCL_ATL_TRANSPORT=ofi
  -e CCL_ZE_IPC_EXCHANGE=pidfd
  -e UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
  --entrypoint /bin/bash
)

VLLM_BASE=(
  --host 0.0.0.0
  --port "${PORT}"
  --served-model-name "${SERVED_NAME}" qwen36-35b-mtp qwen36-35b qwen36-27b-fp8
  --tensor-parallel-size "${TP}"
  --dtype float16
  --quantization fp8
  --mamba-ssm-cache-dtype float16
  --max-model-len "${MAX_LEN}"
  --block-size 128
  --gpu-memory-utilization "${GPU_UTIL}"
  --max-num-seqs "${MAX_SEQS}"
  --max-num-batched-tokens 8192
  --no-enable-prefix-caching
  --enable-auto-tool-choice
  --tool-call-parser qwen3_coder
  --reasoning-parser qwen3
  "--reasoning-config=${REASONING_CONFIG}"
  --trust-remote-code
  "--override-generation-config=${OVERRIDE_GEN}"
  "--default-chat-template-kwargs=${CHAT_TMPL}"
)

if [ "$EAGER" = "1" ]; then
  VLLM_BASE+=(--enforce-eager)
fi
VLLM_CMD=$(printf '%q ' vllm serve "${MODEL}" "${VLLM_BASE[@]}")

# ──────────────────────────────────────────────
# Stop the llama.cpp service that owns port 8001
# ──────────────────────────────────────────────
echo "=== Checking port ${PORT} owner ==="
if systemctl is-active --quiet llama-qwen36-35b.service 2>/dev/null; then
  echo "  Stopping llama-qwen36-35b.service (frees port ${PORT})..."
  systemctl stop llama-qwen36-35b.service
fi
if ss -tln | grep -q ":${PORT} "; then
  echo "  WARNING: something still listens on :${PORT}:"
  ss -tlnp | grep ":${PORT} "
fi

# ──────────────────────────────────────────────
# Cleanup stale container
# ──────────────────────────────────────────────
echo "=== Cleaning up stale ${NAME} ==="
if [ "$(docker ps -a -q -f name=^/${NAME}$)" ]; then
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
fi
sleep 2

# ──────────────────────────────────────────────
# Launch
# ──────────────────────────────────────────────
echo ""
echo "=== Starting Qwen3.6 35B A3B (BF16 -> in-place FP8) TP=${TP} with thinking ==="
echo "  Model: ${MODEL_HOST_DIR}"
echo "  Port: ${PORT}  |  GPUs: 0,1  |  Context: ${MAX_LEN}  |  Max Seqs: ${MAX_SEQS}"
echo ""

docker run -d \
  --name "${NAME}" \
  "${DOCKER_ARGS[@]}" \
  "${IMAGE}" -lc "${VLLM_CMD}"

# ──────────────────────────────────────────────
# Health check loop
# ──────────────────────────────────────────────
echo ""
echo "=== Monitoring engine startup ==="
START_TIME=$(date +%s)
IS_HEALTHY=false

sleep 10

for _ in $(seq 1 60); do
  if [ "$(docker inspect -f '{{.State.Running}}' "${NAME}" 2>/dev/null)" != "true" ]; then
    echo -e "\nCRITICAL: Engine process crashed on startup!"
    docker logs "${NAME}" --tail 40
    exit 1
  fi

  if docker logs "${NAME}" 2>&1 | grep -q "Application startup complete"; then
    IS_HEALTHY=true
    echo -e "\nEngine online after $(( $(date +%s) - START_TIME ))s"
    break
  fi

  echo "  [$(( $(date +%s) - START_TIME ))s] still loading..."
  docker logs "${NAME}" --tail 2
  sleep 20
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
# Smoke tests (plain + thinking)
# ──────────────────────────────────────────────
echo "=== Smoke test: plain ==="
curl -s -H "Content-Type: application/json" http://localhost:${PORT}/v1/chat/completions \
  -d '{"model":"qwen36-35b-fp8","messages":[{"role":"user","content":"Say hello in one word"}],"max_tokens":20,"chat_template_kwargs":{"enable_thinking":false}}' \
  | python3 -m json.tool 2>/dev/null \
  || curl -s -H "Content-Type: application/json" http://localhost:${PORT}/v1/chat/completions \
       -d '{"model":"qwen36-35b-fp8","messages":[{"role":"user","content":"Say hello in one word"}],"max_tokens":20,"chat_template_kwargs":{"enable_thinking":false}}'

echo ""
echo "=== Smoke test: thinking (${THINKING_BUDGET}-token budget) ==="
curl -s -H "Content-Type: application/json" http://localhost:${PORT}/v1/chat/completions \
  -d "{\"model\":\"qwen36-35b-fp8\",\"messages\":[{\"role\":\"user\",\"content\":\"Solve 17*24 step by step\"}],\"max_tokens\":500,\"thinking_token_budget\":${THINKING_BUDGET}}" \
  | python3 -m json.tool 2>/dev/null \
  || curl -s -H "Content-Type: application/json" http://localhost:${PORT}/v1/chat/completions \
       -d "{\"model\":\"qwen36-35b-fp8\",\"messages\":[{\"role\":\"user\",\"content\":\"Solve 17*24 step by step\"}],\"max_tokens\":500,\"thinking_token_budget\":${THINKING_BUDGET}}"

echo ""
echo "=== Done ==="
