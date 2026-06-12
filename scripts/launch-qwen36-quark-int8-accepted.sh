#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${MODEL_PATH:-/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-qwen36-35b-a3b-fp8}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18080}"
LOG_PATH="${LOG_PATH:-/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix.log}"
if [[ -z "${COMPILATION_CONFIG:-}" ]]; then
  COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'
fi
MODEL_INPUT_TRACE_FILE="${MODEL_INPUT_TRACE_FILE:-}"
MODEL_INPUT_TRACE_MAX_LINES="${MODEL_INPUT_TRACE_MAX_LINES:-400}"
MODEL_INPUT_TRACE_RANK="${MODEL_INPUT_TRACE_RANK:-}"
COW_PARENT_TRACE_FILE="${COW_PARENT_TRACE_FILE:-}"
COW_PARENT_TRACE_MAX_LINES="${COW_PARENT_TRACE_MAX_LINES:-2000}"
COW_WORKER_TRACE_FILE="${COW_WORKER_TRACE_FILE:-}"
COW_WORKER_TRACE_MAX_LINES="${COW_WORKER_TRACE_MAX_LINES:-2000}"
COW_WORKER_TRACE_RANK="${COW_WORKER_TRACE_RANK:-}"

export HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-/mnt/fast-ai/llm-cache/hf}"
export TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix/torchinductor}"
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix/vllm}"
export PYTHONPATH="/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

export VLLM_USE_V1=1
export VLLM_TARGET_DEVICE=xpu
export VLLM_ALLOW_LONG_MAX_MODEL_LEN=1
export XPU_GRAPH="${XPU_GRAPH:-1}"
export VLLM_XPU_ENABLE_XPU_GRAPH="${VLLM_XPU_ENABLE_XPU_GRAPH:-1}"
export VLLM_XPU_FORCE_GRAPH_WITH_COMM="${VLLM_XPU_FORCE_GRAPH_WITH_COMM:-1}"
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE="${VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE:-1}"
export VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=1
export VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1
export VLLM_XPU_CUSTOM_ALLREDUCE_GRAPH_CLONE_INPUT=1
export VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1
export VLLM_XPU_QUARK_W8A8_MOE=1
export VLLM_XPU_FORCE_QUARK_REPACK=0
export VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone
export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
export ZE_AFFINITY_MASK=0,1,2,3
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export FI_TCP_IFACE="${FI_TCP_IFACE:-eth1}"
export CCL_KVS_IFACE="${CCL_KVS_IFACE:-eth1}"

unset CCL_ZE_IPC_EXCHANGE
unset CCL_WORKER_COUNT

unset VLLM_XPU_GDN_SKIP_DECODE_CONV_TMP
if [[ "${VLLM_XPU_DECODE_TIMING_ALLOW:-0}" != "1" ]]; then
  unset VLLM_XPU_DECODE_TIMING
  unset VLLM_XPU_DECODE_TIMING_SYNC
  unset VLLM_XPU_DECODE_TIMING_RANK
  unset VLLM_XPU_DECODE_TIMING_SUMMARY
  unset VLLM_XPU_DECODE_TIMING_PRINT_EVERY
  unset VLLM_XPU_DECODE_TIMING_SKIP_FIRST
  unset VLLM_XPU_DECODE_TIMING_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_EXCLUDE_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_SYNC_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_SYNC_EXCLUDE_LABEL_REGEX
  unset VLLM_XPU_DECODE_TIMING_STEP_SUMMARY
  unset VLLM_XPU_DECODE_TIMING_STEP_EVERY
  unset VLLM_XPU_DECODE_TIMING_STEP_SKIP_FIRST
fi
unset VLLM_XPU_DEDUP_INT8_QUANT
if [[ -n "$MODEL_INPUT_TRACE_FILE" ]]; then
  export VLLM_XPU_MODEL_INPUT_TRACE_FILE="$MODEL_INPUT_TRACE_FILE"
  export VLLM_XPU_MODEL_INPUT_TRACE_MAX_LINES="$MODEL_INPUT_TRACE_MAX_LINES"
  if [[ -n "$MODEL_INPUT_TRACE_RANK" ]]; then
    export VLLM_XPU_MODEL_INPUT_TRACE_RANK="$MODEL_INPUT_TRACE_RANK"
  else
    unset VLLM_XPU_MODEL_INPUT_TRACE_RANK
  fi
  rm -f "$MODEL_INPUT_TRACE_FILE"
else
  unset VLLM_XPU_MODEL_INPUT_TRACE_FILE
  unset VLLM_XPU_MODEL_INPUT_TRACE_MAX_LINES
  unset VLLM_XPU_MODEL_INPUT_TRACE_RANK
fi

if [[ -n "$COW_PARENT_TRACE_FILE" ]]; then
  export VLLM_XPU_COW_VERIFIER_TRACE_FILE="$COW_PARENT_TRACE_FILE"
  export VLLM_XPU_COW_VERIFIER_TRACE_MAX_LINES="$COW_PARENT_TRACE_MAX_LINES"
  rm -f "$COW_PARENT_TRACE_FILE"
else
  unset VLLM_XPU_COW_VERIFIER_TRACE_FILE
  unset VLLM_XPU_COW_VERIFIER_TRACE_MAX_LINES
fi

if [[ -n "$COW_WORKER_TRACE_FILE" ]]; then
  export VLLM_XPU_COW_WORKER_TRACE_FILE="$COW_WORKER_TRACE_FILE"
  export VLLM_XPU_COW_WORKER_TRACE_MAX_LINES="$COW_WORKER_TRACE_MAX_LINES"
  if [[ -n "$COW_WORKER_TRACE_RANK" ]]; then
    export VLLM_XPU_COW_WORKER_TRACE_RANK="$COW_WORKER_TRACE_RANK"
  else
    unset VLLM_XPU_COW_WORKER_TRACE_RANK
  fi
  rm -f "$COW_WORKER_TRACE_FILE"
else
  unset VLLM_XPU_COW_WORKER_TRACE_FILE
  unset VLLM_XPU_COW_WORKER_TRACE_MAX_LINES
  unset VLLM_XPU_COW_WORKER_TRACE_RANK
fi

source /home/steve/.venvs/vllm-xpu/bin/activate

EXTRA_ARGS=()
if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARGS=(${VLLM_EXTRA_ARGS})
fi

exec /home/steve/.venvs/vllm-xpu/bin/vllm serve "$MODEL_PATH" \
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
  --compilation-config "$COMPILATION_CONFIG" \
  --generation-config vllm \
  "${EXTRA_ARGS[@]}" \
  >"$LOG_PATH" 2>&1
