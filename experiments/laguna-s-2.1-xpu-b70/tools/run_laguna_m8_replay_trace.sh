#!/usr/bin/env bash
# Paired, one-generation, replay-only PTI trace for the exact Laguna M8 stack.
set -euo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

run_dir="${1:?usage: run_laguna_m8_replay_trace.sh RUN_DIR}"
readonly repo_root=/home/steve/llm-optimizations
readonly vllm_root=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly unitrace=/home/steve/src/pti-gpu/build-unitrace/unitrace
readonly driver="$script_dir/profile_laguna_m8_replay_trace.py"
readonly analyzer="$script_dir/analyze_laguna_m8_replay_trace.py"
readonly idle="$script_dir/capture_laguna_m8_idle_snapshot.py"
readonly expected_vllm=b1cca41292296342fd9f0f7a5621e8d26d7a910d
readonly expected_kernels=4772f727590c51b72add79350b913d098cf67872
readonly expected_unitrace=5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a
readonly expected_pti=a5bab309f4ffdd78bd127035c46f5f75371160f8
declare -a created=()

die() { echo "Laguna M8 replay trace: $*" >&2; exit 2; }
seal() {
  local path
  for path in "${created[@]}"; do
    [[ -e "$path" ]] && chmod -R a-w -- "$path" || true
  done
}
trap 'rc=$?; seal; exit "$rc"' EXIT

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "run root must be on the internal NVMe"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run root must be canonical"
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
for path in "$repo_root" "$vllm_root" "$kernel_root" "$python" "$unitrace" "$driver" "$analyzer" "$idle"; do
  [[ -e "$path" && "$(realpath -e -- "$path")" != /media/* ]] || die "missing or external required path: $path"
done
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
[[ "$(git -C "$vllm_root" rev-parse HEAD)" == "$expected_vllm" ]] || die "vLLM commit drift"
[[ "$(git -C "$kernel_root" rev-parse HEAD)" == "$expected_kernels" ]] || die "kernel commit drift"
[[ "$(git -C /home/steve/src/pti-gpu rev-parse HEAD)" == "$expected_pti" ]] || die "PTI commit drift"
[[ "$(sha256sum "$unitrace" | awk '{print $1}')" == "$expected_unitrace" ]] || die "unitrace binary drift"
[[ "$(sha256sum "$kernel_root/vllm_xpu_kernels/_C.abi3.so" | awk '{print $1}')" == 126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2 ]] || die "_C binary drift"
[[ "$(sha256sum "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" | awk '{print $1}')" == f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8 ]] || die "_xpu_C binary drift"
[[ "$(sha256sum "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" | awk '{print $1}')" == 6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b ]] || die "_moe_C binary drift"
[[ "$(sha256sum "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" | awk '{print $1}')" == fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96 ]] || die "grouped-GEMM binary drift"
laguna_nvme_verify_model_contents
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || die "existing vLLM worker"

laguna_nvme_prepare_run_dir "$run_dir"
created+=("$run_dir")
chmod 700 "$run_dir"
for arm in eager graph; do
  arm_dir="$run_dir/$arm"
  rpc_dir="$LAGUNA_NVME_TMP_ROOT/m8rt-$arm"
  [[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "reused RPC path: $rpc_dir"
  created+=("$rpc_dir")
  mkdir --mode=700 "$rpc_dir"
  mkdir -p "$arm_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
  chmod -R 700 "$arm_dir"
done

"$python" "$idle" --output "$run_dir/pre-idle.json" || die "preflight device idle check failed"
{
  printf 'schema=laguna-m8-replay-trace-v1\n'
  printf 'purpose=diagnostic-only replay decomposition; never endpoint or submission evidence\n'
  printf 'one_generation_per_fresh_process=true\nprefix_cache=false\nraw_evidence_timing=false\n'
  printf 'vllm=%s\nkernels=%s\npti=%s\nunitrace_sha256=%s\n' \
    "$expected_vllm" "$expected_kernels" "$expected_pti" "$expected_unitrace"
  sha256sum "$0" "$driver" "$analyzer" "$idle"
} > "$run_dir/identity.txt"

run_arm() {
  local arm="$1" graph=0 arm_dir="$run_dir/$1" rpc_dir="$LAGUNA_NVME_TMP_ROOT/m8rt-$1"
  local session random status
  [[ "$arm" == graph ]] && graph=1
  random="$(tr -d '-' < /proc/sys/kernel/random/uuid)"
  session="LagunaReplay${random}"
  printf '%s\n' "$session" > "$arm_dir/session.txt"
  "$python" "$idle" --output "$arm_dir/pre-idle.json" || die "$arm preflight idle check failed"
  set +e
  (
    cd "$arm_dir"
    /usr/bin/timeout --preserve-status --signal=TERM --kill-after=30s 2400s /usr/bin/env -i \
      PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
      HOME="$arm_dir/private-home" TMP="$arm_dir/private-tmp" TEMP="$arm_dir/private-tmp" TMPDIR="$arm_dir/private-tmp" \
      HF_HOME="$arm_dir/private-cache/hf" HF_HUB_CACHE="$arm_dir/private-cache/hf/hub" TRANSFORMERS_CACHE="$arm_dir/private-cache/hf/transformers" \
      VLLM_CACHE_ROOT="$arm_dir/private-cache/vllm" TORCHINDUCTOR_CACHE_DIR="$arm_dir/private-cache/torchinductor" TRITON_CACHE_DIR="$arm_dir/private-cache/triton" SYCL_CACHE_DIR="$arm_dir/private-cache/sycl" NUMBA_CACHE_DIR="$arm_dir/private-cache/numba" PYTHONPYCACHEPREFIX="$arm_dir/private-cache/pycache" \
      XDG_CACHE_HOME="$arm_dir/private-cache" XDG_CONFIG_HOME="$arm_dir/private-xdg/config" XDG_DATA_HOME="$arm_dir/private-xdg/data" XDG_STATE_HOME="$arm_dir/private-xdg/state" \
      PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 PYTHONPATH="$script_dir:$vllm_root:$kernel_root" \
      HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD= \
      ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
      LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
      VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 \
      VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1 VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1 VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 \
      VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 \
      VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7 \
      VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
      VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION="$session" VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE="$unitrace" VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE_SHA256="$expected_unitrace" \
      "$unitrace" --host-timing --device-timing --kernel-submission --verbose --pid --start-paused --session "$session" --output unitrace \
      "$python" "$driver" --arm "$arm" --out "$arm_dir/driver.json" --unitrace "$unitrace" --session "$session" \
      >"$arm_dir/stdout.log" 2>"$arm_dir/stderr.log"
  )
  status=$?
  set -e
  (( status == 0 )) || die "$arm trace failed with status $status"
  ! pgrep -f 'VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || die "$arm left vLLM workers"
  "$python" "$idle" --output "$arm_dir/post-idle.json" || die "$arm postflight idle check failed"
  mv "$rpc_dir" "$arm_dir/rpc-after-stop"
}

run_arm eager
run_arm graph
"$python" "$analyzer" --run-dir "$run_dir" --out "$run_dir/analysis.json"
"$python" "$idle" --output "$run_dir/post-idle.json" || die "postflight device idle check failed"
printf 'status=PASS\n' > "$run_dir/status.txt"
echo "Laguna M8 paired replay trace PASS: $run_dir"
