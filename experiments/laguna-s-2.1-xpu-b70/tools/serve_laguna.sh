#!/usr/bin/env bash
set -euo pipefail

mode="${1:?usage: serve_laguna.sh MODE RUN_DIR [KV_CACHE_DTYPE]}"
run_dir="${2:?usage: serve_laguna.sh MODE RUN_DIR [KV_CACHE_DTYPE]}"
kv_cache_dtype="${3:-auto}"

case "$mode" in
  eager|piecewise|dflash|dflash-piecewise) ;;
  *) echo "unsupported mode: $mode" >&2; exit 2 ;;
esac

case "$kv_cache_dtype" in
  auto|bfloat16|fp8) ;;
  *) echo "unsupported KV cache dtype: $kv_cache_dtype" >&2; exit 2 ;;
esac

artifact_root=/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1
cache_root="$artifact_root/cache"
model_root="$artifact_root/int4"
draft_root="${LAGUNA_DFLASH_ROOT:-$artifact_root/dflash}"
venv_root=/home/steve/.venvs/deepseek-v4-xpu
vllm_root=/home/steve/src/deepseek-v4-vllm-xpu-dspark
kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc

mkdir -p "$run_dir" "$cache_root/hf" "$cache_root/vllm" \
  "$cache_root/torchinductor" "$cache_root/triton" "$cache_root/tmp"

source "$venv_root/bin/activate"
export PYTHONPATH="$vllm_root:$kernel_root${PYTHONPATH:+:$PYTHONPATH}"
export ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3
export ZE_AFFINITY_MASK=0,1,2,3
export CCL_ATL_TRANSPORT=ofi
export CCL_TOPO_P2P_ACCESS=1
export HF_HOME="$cache_root/hf"
export HF_HUB_CACHE="$cache_root/hf/hub"
export TRANSFORMERS_CACHE="$cache_root/hf/transformers"
export VLLM_CACHE_ROOT="$cache_root/vllm"
export TORCHINDUCTOR_CACHE_DIR="$cache_root/torchinductor"
export TRITON_CACHE_DIR="$cache_root/triton"
export XDG_CACHE_HOME="$cache_root"
# Keep the ZMQ IPC pathname below Linux's sockaddr_un limit. This symlink's
# target is $cache_root/tmp, so temporary state remains on the external drive.
export TMPDIR=/media/steve/CorsairExternal/l21tmp
export VLLM_KV_CACHE_LAYOUT=NHD

common_args=(
  "$model_root"
  --host 127.0.0.1 --port 18080
  --served-model-name laguna-s-2.1-int4
  --dtype bfloat16
  --tensor-parallel-size 4
  --data-parallel-size 1
  --pipeline-parallel-size 1
  --distributed-executor-backend mp
  --enable-expert-parallel
  --all2all-backend allgather_reducescatter
  --max-model-len 8192
  --max-num-batched-tokens 8192
  --max-num-seqs 1
  --block-size 64
  --kv-cache-dtype "$kv_cache_dtype"
  --gpu-memory-utilization 0.90
  --no-enable-prefix-caching
  --generation-config vllm
  --enable-prompt-tokens-details
)

if [[ "$mode" != piecewise && "$mode" != dflash-piecewise ]]; then
  export XPU_GRAPH=0
  export VLLM_XPU_ENABLE_XPU_GRAPH=0
  common_args+=(--enforce-eager)
else
  export XPU_GRAPH=1
  export VLLM_XPU_ENABLE_XPU_GRAPH=1
  export TRITON_INTEL_DISABLE_IGC_OPT=1
  common_args+=(--compilation-config '{"custom_ops":["all"],"use_inductor_graph_partition":true,"compile_sizes":[1],"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":1}')
fi

if [[ "$mode" == dflash || "$mode" == dflash-piecewise ]]; then
  # Async scheduling races the completed DFlash request with the following
  # target prefill on XPU. Serialize the DFlash scheduler/model-runner handoff.
  # Keep the q=1 teacher's original scheduling contract: its target arithmetic
  # changes when async scheduling is disabled even without speculation.
  common_args+=(--no-async-scheduling)
  common_args+=(--speculative-config "{\"method\":\"dflash\",\"model\":\"$draft_root\",\"num_speculative_tokens\":7,\"draft_sample_method\":\"greedy\",\"rejection_sample_method\":\"standard\"}")
fi

if [[ -n "${VLLM_EXTRA_ARGS:-}" ]]; then
  read -r -a extra_args <<< "$VLLM_EXTRA_ARGS"
  common_args+=("${extra_args[@]}")
fi

exec vllm serve "${common_args[@]}"
