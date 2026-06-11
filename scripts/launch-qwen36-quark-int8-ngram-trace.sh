#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${MODEL_PATH:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-35b-a3b-fp8}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18080}"
NUM_SPECULATIVE_TOKENS="${NUM_SPECULATIVE_TOKENS:-1}"
PROMPT_LOOKUP_MIN="${PROMPT_LOOKUP_MIN:-2}"
PROMPT_LOOKUP_MAX="${PROMPT_LOOKUP_MAX:-5}"
TAG="${TAG:-ngram${NUM_SPECULATIVE_TOKENS}-trace}"
LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-${TAG}-20260611.log}"
SPEC_TRACE_FILE="${SPEC_TRACE_FILE:-/tmp/qwen36-${TAG}-spec-trace-20260611.jsonl}"
SPEC_TRACE_MAX_LINES="${SPEC_TRACE_MAX_LINES:-20000}"
ENABLE_XPU_GRAPH="${ENABLE_XPU_GRAPH:-1}"
ENFORCE_EAGER="${ENFORCE_EAGER:-0}"
CUDAGRAPH_CAPTURE_SIZES="${CUDAGRAPH_CAPTURE_SIZES:-}"
COMPILE_CONFIG="${COMPILE_CONFIG:-{\"cudagraph_mode\":\"PIECEWISE\",\"max_cudagraph_capture_size\":128}}"
DISABLE_FULL_ACCEPT_BONUS="${DISABLE_FULL_ACCEPT_BONUS:-0}"

if [[ -n "$CUDAGRAPH_CAPTURE_SIZES" ]]; then
  COMPILE_CONFIG=$(printf '{"cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[%s],"max_cudagraph_capture_size":128}' \
    "$CUDAGRAPH_CAPTURE_SIZES")
fi

export HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-/mnt/fast-ai/llm-cache/hf}"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-${TAG}-20260611/torchinductor}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-${TAG}-20260611/vllm}"
export PYTHONPATH="/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

export VLLM_USE_V1=1
export VLLM_TARGET_DEVICE=xpu
export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
export XPU_GRAPH="$ENABLE_XPU_GRAPH"
export VLLM_XPU_ENABLE_XPU_GRAPH="$ENABLE_XPU_GRAPH"
if [[ "$ENABLE_XPU_GRAPH" == "1" ]]; then
  export VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
  export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
else
  unset VLLM_XPU_FORCE_GRAPH_WITH_COMM
  unset VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE
fi
export VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1
export VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1
export VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1
export VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1
export VLLM_XPU_QUARK_W8A8_MOE=1
export VLLM_XPU_FORCE_QUARK_REPACK=0
export VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone
export VLLM_XPU_HOLD_SPEC_DECODE_WHEN_WAITING=1
export VLLM_SPEC_DECODE_TRACE_FILE="$SPEC_TRACE_FILE"
export VLLM_SPEC_DECODE_TRACE_MAX_LINES="$SPEC_TRACE_MAX_LINES"
if [[ "$DISABLE_FULL_ACCEPT_BONUS" == "1" ]]; then
  export VLLM_XPU_SPEC_DECODE_DISABLE_FULL_ACCEPT_BONUS=1
else
  unset VLLM_XPU_SPEC_DECODE_DISABLE_FULL_ACCEPT_BONUS
fi
export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
export ZE_AFFINITY_MASK=0,1,2,3
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export FI_TCP_IFACE="${FI_TCP_IFACE:-eth1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eth1}"

unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT

unset VLLM_XPU_DISABLE_SPEC_DECODE_WHEN_WAITING
unset VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP
unset VLLM_XPU_DECODE_TIMING
unset VLLM_XPU_DEDUP_INT8_QUANT

source /home/steve/.venvs/vllm-xpu/bin/activate

rm -f "$SPEC_TRACE_FILE"

SPEC_CONFIG=$(printf '{"method":"ngram","num_speculative_tokens":%s,"prompt_lookup_min":%s,"prompt_lookup_max":%s}' \
  "$NUM_SPECULATIVE_TOKENS" "$PROMPT_LOOKUP_MIN" "$PROMPT_LOOKUP_MAX")

args=(
  serve "$MODEL_PATH"
  --host "$HOST" \
  --port "$PORT" \
  --trust-remote-code \
  --served-model-name "$SERVED_MODEL_NAME" \
  --dtype auto \
  --quantization quark \
  --tensor-parallel-size 4 \
  --pipeline-parallel-size 1 \
  --distributed-executor-backend mp \
  --max-model-len 32768 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 48 \
  --gpu-memory-utilization 0.95 \
  --kv-cache-dtype auto \
  --no-enable-prefix-caching \
  --language-model-only \
  --speculative-config "$SPEC_CONFIG" \
  --generation-config vllm
)

if [[ -n "$COMPILE_CONFIG" ]]; then
  args+=(--compilation-config "$COMPILE_CONFIG")
fi

if [[ "$ENFORCE_EAGER" == "1" ]]; then
  args+=(--enforce-eager)
fi

exec /home/steve/.venvs/vllm-xpu/bin/vllm "${args[@]}" >"$LOG_PATH" 2>&1
