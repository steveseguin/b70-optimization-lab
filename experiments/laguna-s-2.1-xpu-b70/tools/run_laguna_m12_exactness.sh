#!/usr/bin/env bash
# Eager exactness arms at two verifier widths. Diagnostic only.
set -euo pipefail
umask 077
readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
readonly vllm=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernels=/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly tools=/home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools
readonly root="${1:?usage: RUN_ROOT}"; readonly spec="${2:?usage: SPEC_TOKENS}"; readonly maxm="${3:?usage: MAX_M}"
readonly rpc="${LAGUNA_NVME_TMP_ROOT:-/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp}/m12x"
die(){ echo "m12 exactness: $*" >&2; exit 2; }
[[ -z "$(git -C "$vllm" status --porcelain=v1)" ]] || die "vLLM worktree dirty"
[[ -e "$rpc" ]] && rm -rf -- "$rpc"
for d in 0 1 2 3; do
  u="$(timeout 15 xpu-smi stats -d "$d" 2>/dev/null | awk -F'|' '/GPU Memory Used/{gsub(/ /,"",$3);print $3}')"
  [[ -n "$u" && "$u" -lt 1024 ]] || die "card $d busy (${u:-?} MiB)"
done
mkdir -p -- "$root"/{private-home,private-cache/{hf,vllm,torchinductor,triton,sycl,numba},private-xdg/{config,data,state}}
mkdir --mode=700 -- "$rpc"; trap 'rm -rf -- "$rpc"' EXIT
setsid /usr/bin/timeout --foreground --preserve-status --signal=TERM --kill-after=60s 5400s \
  /usr/bin/env -i PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  HOME="$root/private-home" TMPDIR="$rpc" VLLM_RPC_BASE_PATH="$rpc" \
  HF_HOME="$root/private-cache/hf" HF_HUB_CACHE="$root/private-cache/hf/hub" \
  VLLM_CACHE_ROOT="$root/private-cache/vllm" \
  TORCHINDUCTOR_CACHE_DIR="$root/private-cache/torchinductor" \
  TRITON_CACHE_DIR="$root/private-cache/triton" SYCL_CACHE_DIR="$root/private-cache/sycl" \
  NUMBA_CACHE_DIR="$root/private-cache/numba" XDG_CACHE_HOME="$root/private-cache" \
  XDG_CONFIG_HOME="$root/private-xdg/config" XDG_DATA_HOME="$root/private-xdg/data" \
  XDG_STATE_HOME="$root/private-xdg/state" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 PYTHONPATH="$vllm:$kernels" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 OMP_NUM_THREADS=1 LD_PRELOAD= \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 \
  CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 \
  TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
  LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE="${MOE:-1}" \
  VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2="${W1:-1}" VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE="${RI:-1}" \
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE="${SE:-1}" VLLM_XPU_LAGUNA_M8_QKNORM_ROPE="${QK:-1}" \
  VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 VLLM_XPU_LAGUNA_EXACT_MAX_M="$maxm" \
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=0 VLLM_USE_BREAKABLE_CUDAGRAPH=0 XPU_GRAPH=0 \
  VLLM_XPU_ENABLE_XPU_GRAPH=0 VLLM_USE_AOT_COMPILE=0 VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 \
  VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=0 \
  LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS="$spec" \
  "$python" "$tools/run_laguna_m12_exactness_arm.py" --out "$root/arm.json" \
    --speculative-tokens "$spec" --max-tokens 128 \
  >"$root/driver.stdout" 2>"$root/driver.stderr"
echo "arm done: $root"
