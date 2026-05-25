#!/usr/bin/env bash
set -euo pipefail

# Reproduces or verifies the MiniMax + TurboQuant XPU workspace issue.
# Expected result on the unpatched 2026-05-23 B70 stack:
# - server reaches /v1/models
# - vLLM reports larger KV capacity
# - first completion returns HTTP 500 with a TurboQuant workspace allocation
#   assertion in turboquant_attn.py:_decode_attention
# Expected result after applying
# patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch:
# - server reaches /v1/models
# - first completion returns HTTP 200

LOG_DIR="${LOG_DIR:-/mnt/fast-ai/bench-results/minimax-m27-b70-turboquant-20260523}"
PORT="${PORT:-18080}"
KV_DTYPE="${KV_DTYPE:-turboquant_k8v4}"
MODEL_NAME="${MODEL_NAME:-minimax-tq-k8v4}"
mkdir -p "$LOG_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
log="$LOG_DIR/server-${KV_DTYPE}-ctx32768-${ts}.log"

source /home/steve/.venvs/vllm-xpu/bin/activate
# The promoted environment and vLLM wrapper already carry the runtime paths on
# this lab machine. Intel's vars.sh may exit under strict shell options, which
# hides the TurboQuant failure this script is meant to reproduce. Opt in only
# when testing a fresh shell that truly needs it.
if [ "${SOURCE_ONEAPI_ENV:-0}" = "1" ]; then
  source /opt/intel/oneapi/compiler/2025.3/env/vars.sh >/dev/null 2>&1 || true
fi
source /home/steve/llm-optimizations/repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh

cleanup() {
  if [ -n "${server_pid:-}" ] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

vllm serve "$MODEL" \
  --served-model-name "$MODEL_NAME" \
  --host 127.0.0.1 \
  --port "$PORT" \
  --trust-remote-code \
  --dtype float16 \
  --tensor-parallel-size 4 \
  --distributed-executor-backend mp \
  --max-model-len 32768 \
  --max-num-batched-tokens 512 \
  --max-num-seqs 1 \
  --gpu-memory-utilization 0.95 \
  --block-size 256 \
  --no-enable-prefix-caching \
  --compilation-config '{"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE"}' \
  --kv-cache-dtype "$KV_DTYPE" \
  >"$log" 2>&1 &
server_pid=$!

for _ in $(seq 1 240); do
  if curl -fsS "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    tail -160 "$log" >&2 || true
    exit 1
  fi
  sleep 2
done

curl -fsS "http://127.0.0.1:${PORT}/v1/models" | jq '.data[0] | {id,max_model_len}'

set +e
curl -sS -w "\nhttp_status=%{http_code}\n" "http://127.0.0.1:${PORT}/v1/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${MODEL_NAME}\",\"prompt\":\"Write one sentence about quality gates.\",\"max_tokens\":32,\"temperature\":0}"
status=$?
set -e

echo "curl_exit=$status"
echo "log=$log"
rg -n "GPU KV cache size|Maximum concurrency|Workspace is locked|turboquant_attn|ocloc|Internal Compiler Error" "$log" || true
exit "$status"
