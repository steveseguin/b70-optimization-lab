#!/usr/bin/env bash
set -euo pipefail

# Source this file before quality or benchmark runs.
# Override these before sourcing if your machine uses different paths.
export MODEL="${MODEL:-/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround}"
export VENV="${VENV:-$HOME/.venvs/vllm-xpu}"
export LLM_SCALER_KERNELS="${LLM_SCALER_KERNELS:-$HOME/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python}"
# Keep this in a cache namespace that has passed the raw145 n64+n256 gate.
# The older 20260519 cache root produced a deterministic but wrong n256 hash
# on 2026-05-21, so do not reuse stale compiled artifacts blindly.
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-/mnt/fast-ai/vllm-cache-exp/minimax-quality-clean-20260521T152425Z}"
export HF_HOME="${HF_HOME:-/mnt/fast-ai/llm-cache/hf}"
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"

if [ -z "${B70_CCL_IFACE:-}" ]; then
  B70_CCL_IFACE="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}' || true)"
fi
if [ -n "${B70_CCL_IFACE:-}" ]; then
  export FI_TCP_IFACE="${FI_TCP_IFACE:-$B70_CCL_IFACE}"
  export CCL_KVS_IFACE="${CCL_KVS_IFACE:-$B70_CCL_IFACE}"
fi

export ONEAPI_DEVICE_SELECTOR="${ONEAPI_DEVICE_SELECTOR:-level_zero:0,1,2,3}"
export ZE_AFFINITY_MASK="${ZE_AFFINITY_MASK:-0,1,2,3}"
export CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}"
export CCL_TOPO_P2P_ACCESS="${CCL_TOPO_P2P_ACCESS:-1}"

export VLLM_XPU_USE_LLM_SCALER_MOE=1
export VLLM_XPU_USE_LLM_SCALER_MOE_WS=1
export VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS=1
export VLLM_MINIMAX_M2_ATTN_DELAY_ALLREDUCE=0
# Do not enable upstream-style XPU custom-op collectives on this stack.
# The 2026-05-21 raw145 canary produced NUL/control output when this was set.
export VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES=0
export VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=1
export VLLM_XPU_CUSTOM_ALLREDUCE_CLONE_INPUT=1
export VLLM_XPU_CUSTOM_ALLREDUCE_TINY_FP32_INPLACE_MAX_NUMEL=2
export VLLM_XPU_CUSTOM_ALLREDUCE_INPLACE_MAX_NUMEL=0
export VLLM_MINIMAX_QK_RMS_XPU_HELPER=1
export VLLM_MINIMAX_QK_RMS_XPU_HELPER_MAX_TOKENS=4
export VLLM_MINIMAX_QK_RMS_DIRECT_INPLACE_SCALE=1
export VLLM_MINIMAX_QK_RMS_APPLY_TP_SCALE=0
export VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT=1
export VLLM_MINIMAX_QK_NORM_RESTORE_WEIGHT_MIN_TOKENS=2
export VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=1
export VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=1
export VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS=4
export VLLM_MINIMAX_POST_ATTN_NORM_MOE_CUSTOM_OP=0
export VLLM_XPU_ENABLE_XPU_GRAPH=1
export VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
export VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1

export PYTHONPATH="$LLM_SCALER_KERNELS:${PYTHONPATH:-}"
export LD_LIBRARY_PATH="$VENV/lib:$VENV/lib/python3.12/site-packages/torch/lib:${LD_LIBRARY_PATH:-}"
