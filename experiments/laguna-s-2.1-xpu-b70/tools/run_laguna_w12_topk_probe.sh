#!/usr/bin/env bash
# Width-12 top-k probe: does the drafter's rank-2 token rescue rejections?
# Diagnostic only. Measures the quantity the tree projection rests on --
# how often, when the top-1 draft is rejected, the target's actual token is
# the drafter's second choice. Produces no throughput claim.
# Diagnostic only: produces attribution, never a throughput claim.
set -euo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
readonly repo=/home/steve/llm-optimizations
readonly vllm=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernels=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly tools="$repo/experiments/laguna-s-2.1-xpu-b70/tools"
readonly driver="$tools/run_laguna_w12_topk_probe_arm.py"
readonly root="${1:?usage: run_laguna_phase0_cycle_attribution.sh RUN_ROOT}"
readonly expected_vllm="$(git -C "$vllm" rev-parse --short=9 HEAD)"
# zmq ipc sockets live here; the path must stay well under 107 characters
readonly rpc="${LAGUNA_NVME_TMP_ROOT:-/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp}/w12topk"

die() { echo "w12 topk probe: $*" >&2; exit 2; }

# Resolve the interface carrying the cluster IP; a reboot on 2026-07-26 moved it
# from eno1 to eth1 and oneCCL fails KVS bootstrap when the name is wrong.
cluster_iface="$(ip -o -4 addr show 2>/dev/null | awk -v ip="${LAGUNA_CLUSTER_IP:-10.0.0.65}" '$4 ~ "^"ip"/" {print $2; exit}')"
[[ -n "$cluster_iface" ]] || { echo "no interface carries the cluster IP" >&2; exit 2; }
readonly cluster_iface

[[ "$(git -C "$vllm" rev-parse --short=9 HEAD)" == "$expected_vllm" ]] ||
  die "vLLM identity drift"
[[ -z "$(git -C "$vllm" status --porcelain=v1)" ]] || die "vLLM worktree dirty"
[[ -e "$root" ]] && die "run root already exists"
[[ -e "$rpc" ]] && die "refusing reused rpc path: $rpc"

pgrep -f 'vllm serve|torchrun|EngineCore' >/dev/null && die "existing worker blocks the run"
for d in 0 1 2 3; do
  used="$(timeout 15 xpu-smi stats -d "$d" 2>/dev/null |
          awk -F'|' '/GPU Memory Used/ {gsub(/ /,"",$3); print $3}')"
  [[ -n "$used" && "$used" -lt 1024 ]] || die "card $d is not idle (${used:-unknown} MiB)"
done

mkdir -p -- "$root"/{attribution,private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
chmod -R 700 -- "$root"
mkdir --mode=700 -- "$rpc"
trap 'rm -rf -- "$rpc"' EXIT

echo "w12 topk probe run root: $root"
setsid /usr/bin/timeout --foreground --preserve-status --signal=TERM --kill-after=60s 5400s \
  /usr/bin/env -i \
  PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  HOME="$root/private-home" TMPDIR="$rpc" \
  VLLM_RPC_BASE_PATH="$rpc" \
  HF_HOME="$root/private-cache/hf" HF_HUB_CACHE="$root/private-cache/hf/hub" \
  VLLM_CACHE_ROOT="$root/private-cache/vllm" \
  TORCHINDUCTOR_CACHE_DIR="$root/private-cache/torchinductor" \
  TRITON_CACHE_DIR="$root/private-cache/triton" \
  SYCL_CACHE_DIR="$root/private-cache/sycl" \
  NUMBA_CACHE_DIR="$root/private-cache/numba" \
  PYTHONPYCACHEPREFIX="$root/private-cache/pycache" \
  XDG_CACHE_HOME="$root/private-cache" \
  XDG_CONFIG_HOME="$root/private-xdg/config" \
  XDG_DATA_HOME="$root/private-xdg/data" \
  XDG_STATE_HOME="$root/private-xdg/state" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHASHSEED=0 \
  PYTHONPATH="$vllm:$kernels" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD= \
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 \
  CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE="$cluster_iface" \
  CCL_KVS_IFACE="$cluster_iface" TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
  LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 \
  VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 \
  VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 \
  VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 \
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1 \
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1 \
  VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1 \
  VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1 \
  VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=0 \
  VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 \
  VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 \
  VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 \
  VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 \
  VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 \
  VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 \
  VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 \
  VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 \
  VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 \
  VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 \
  VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 \
  LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=11 VLLM_XPU_LAGUNA_EXACT_MAX_M=12 \
  VLLM_USE_BREAKABLE_CUDAGRAPH=1 XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
  VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_ROOT="$root/attribution" \
  VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_DEVICE_CYCLES=1 \
  VLLM_XPU_LAGUNA_CYCLE_ATTRIBUTION_TOPK_PROBE=1 \
  "$python" "$driver" --out "$root/arm.json" \
  >"$root/driver.stdout" 2>"$root/driver.stderr"

echo "w12 topk probe complete"
ls -la "$root/attribution"
