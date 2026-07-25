#!/usr/bin/env bash
# Fresh-process q1/eager/graph replay telemetry gate; never benchmark evidence.
set -euo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

run_dir="${1:?usage: run_laguna_m8_inprocess_replay.sh RUN_DIR}"
readonly repo_root=/home/steve/llm-optimizations
readonly vllm_root=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly driver="$script_dir/run_laguna_m8_inprocess_replay_arm.py"
readonly analyzer="$script_dir/analyze_laguna_m8_inprocess_replay.py"
readonly idle="$script_dir/capture_laguna_m8_idle_snapshot.py"
readonly expected_vllm=8cf58ed0f3679245053b6f298b4bf1ccd13906ed
readonly expected_kernels=4772f727590c51b72add79350b913d098cf67872
readonly record_vllm=0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca
readonly record_kernels=b6076ce1249ffee0e30bee528f4cd15c3bffb234
declare -a created=()
active_pg=""

die() { echo "Laguna M8 in-process replay: $*" >&2; exit 2; }

cleanup_active_pg() {
  local signal attempt
  [[ "$active_pg" =~ ^[1-9][0-9]*$ ]] || return 0
  for signal in TERM KILL; do
    kill -0 -- "-$active_pg" 2>/dev/null || break
    kill "-$signal" -- "-$active_pg" 2>/dev/null || true
    for attempt in $(seq 1 10); do
      kill -0 -- "-$active_pg" 2>/dev/null || break
      sleep 1
    done
  done
}

seal() {
  local path
  for path in "${created[@]}"; do
    [[ -e "$path" ]] && chmod -R a-w -- "$path" || true
  done
}
trap 'rc=$?; cleanup_active_pg; seal; exit "$rc"' EXIT

assert_no_workers() {
  local report="$1"
  "$python" - "$report" <<'PY'
import os
import sys
from pathlib import Path

report = Path(sys.argv[1])
ancestors: set[int] = set()
pid = os.getpid()
while pid > 1 and pid not in ancestors:
    ancestors.add(pid)
    try:
        pid = int(Path(f"/proc/{pid}/stat").read_text().split()[3])
    except (OSError, ValueError, IndexError):
        break

matches: list[str] = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) in ancestors:
        continue
    try:
        argv = [
            part.decode("utf-8", "replace")
            for part in (proc / "cmdline").read_bytes().split(b"\0")
            if part
        ]
        comm = (proc / "comm").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        continue
    if not argv:
        continue
    basename = Path(argv[0]).name
    is_serve = any(
        argv[index] == "vllm" and argv[index + 1] == "serve"
        for index in range(len(argv) - 1)
    )
    is_worker = comm.startswith("VLLM::") or any(
        value.startswith(("VLLM::EngineCore", "VLLM::Worker"))
        for value in argv
    )
    is_torchrun = basename == "torchrun" or (
        len(argv) >= 3
        and basename.startswith("python")
        and argv[1:3] == ["-m", "torch.distributed.run"]
    )
    if is_serve or is_worker or is_torchrun:
        matches.append(f"{proc.name}\t{comm}\t{' '.join(argv)}")

flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
fd = os.open(report, flags, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write("\n".join(matches))
    if matches:
        handle.write("\n")
if matches:
    print("\n".join(matches), file=sys.stderr)
    raise SystemExit(1)
PY
}

capture_idle() {
  "$python" "$idle" --output "$1"
}

check_hash() {
  local path="$1" expected="$2" actual
  actual="$(sha256sum -- "$path" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || die "SHA256 mismatch for $path"
}

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "run root must be on internal NVMe"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run root must be canonical"
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
run_tag="$(printf '%s' "$run_dir" | sha256sum | cut -c1-12)"
readonly run_tag

ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited runtime variables: $ambient_sensitive"

for path in "$repo_root" "$vllm_root" "$kernel_root" "$python" "$driver" "$analyzer" "$idle"; do
  [[ -e "$path" && "$(realpath -e -- "$path")" != /media/* ]] || die "missing or external required path: $path"
done
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
[[ "$(git -C "$vllm_root" rev-parse HEAD)" == "$expected_vllm" ]] || die "vLLM commit drift"
[[ "$(git -C "$kernel_root" rev-parse HEAD)" == "$expected_kernels" ]] || die "kernel commit drift"
git -C "$vllm_root" merge-base --is-ancestor "$record_vllm" "$expected_vllm" \
  || die "telemetry runtime is not an approved-record descendant"
git -C "$kernel_root" merge-base --is-ancestor "$record_kernels" "$expected_kernels" \
  || die "kernel runtime is not an approved-record descendant"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" 126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" 6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96

created+=("$run_dir")
laguna_nvme_prepare_run_dir "$run_dir"
chmod 700 -- "$run_dir"
for arm in q1 eager graph; do
  arm_dir="$run_dir/$arm"
  rpc_dir="$LAGUNA_NVME_TMP_ROOT/i${run_tag:0:8}${arm:0:1}"
  (( ${#rpc_dir} + 1 + 36 <= 107 )) || die "projected ZMQ IPC path is too long"
  [[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "reused RPC path: $rpc_dir"
  mkdir --mode=700 -- "$rpc_dir"
  created+=("$rpc_dir")
  mkdir -p -- "$arm_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
  chmod -R 700 -- "$arm_dir"
done

assert_no_workers "$run_dir/pre-workers.txt" || die "existing vLLM/torchrun worker blocks campaign"
capture_idle "$run_dir/pre-idle.json" || die "strict pre-campaign device idle proof failed"
laguna_nvme_verify_model_contents
{
  printf 'schema=laguna-m8-inprocess-replay-v1\n'
  printf 'purpose=diagnostic-only in-process replay telemetry; never benchmark or submission evidence\n'
  printf 'arms=q1,eager,graph; one_generation_per_fresh_process=true\n'
  printf 'vllm=%s\nkernels=%s\n' "$expected_vllm" "$expected_kernels"
  printf 'run_tag=%s\n' "$run_tag"
  printf 'graph_telemetry_only=true\ngraph_profile_samples=31\n'
  sha256sum "$0" "$driver" "$analyzer" "$idle" "$script_dir/laguna_nvme_paths.sh"
} > "$run_dir/identity.txt"

run_arm() {
  local arm="$1" graph=0 arm_dir="$run_dir/$1"
  local rpc_dir="$LAGUNA_NVME_TMP_ROOT/i${run_tag:0:8}${1:0:1}"
  local profile_dir="" status post_status=0 had_survivors=0 attempt
  local optimized_dflash=1
  local -a profile_env=() selector_env=() driver_args=()
  [[ "$arm" == graph ]] && graph=1
  [[ "$arm" == q1 ]] && optimized_dflash=0
  selector_env=(
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=$optimized_dflash"
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=$optimized_dflash"
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=$optimized_dflash"
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=$optimized_dflash"
  )
  driver_args=("$python" "$driver" --arm "$arm" --out "$arm_dir/driver.json")
  if (( graph )); then
    profile_dir="$arm_dir/replay-profile"
    mkdir --mode=700 -- "$profile_dir"
    profile_env=(
      "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT=$profile_dir"
      "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES=31"
    )
    driver_args+=(--profile-root "$profile_dir")
  fi

  assert_no_workers "$arm_dir/pre-workers.txt" || die "existing worker blocks $arm arm"
  capture_idle "$arm_dir/pre-idle.json" || die "strict pre-arm idle proof failed for $arm"
  set +e
  (
    cd -- "$arm_dir"
    exec setsid /usr/bin/timeout --preserve-status --signal=TERM --kill-after=30s 2400s /usr/bin/env -i \
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
      "${selector_env[@]}" VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 \
      VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 \
      VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7 \
      VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
      "${profile_env[@]}" "${driver_args[@]}" \
      >"$arm_dir/stdout.log" 2>"$arm_dir/stderr.log"
  ) &
  active_pg="$!"
  wait "$active_pg"
  status=$?
  set -e
  for attempt in $(seq 1 10); do
    kill -0 -- "-$active_pg" 2>/dev/null || break
    sleep 1
  done
  if kill -0 -- "-$active_pg" 2>/dev/null; then
    had_survivors=1
    cleanup_active_pg
  fi
  active_pg=""
  assert_no_workers "$arm_dir/post-workers.txt" || post_status=1
  capture_idle "$arm_dir/post-idle.json" || post_status=1
  (( status == 0 )) || die "$arm arm failed with status $status"
  (( had_survivors == 0 )) || die "$arm arm left its process group alive"
  (( post_status == 0 )) || die "$arm arm left workers or non-idle XPUs"
  mv -- "$rpc_dir" "$arm_dir/rpc-after-stop"
}

run_arm q1
run_arm eager
run_arm graph
"$python" "$analyzer" --run-dir "$run_dir" --out "$run_dir/analysis.json"
capture_idle "$run_dir/post-idle.json" || die "strict post-campaign device idle proof failed"
printf 'status=PASS\n' > "$run_dir/status.txt"
echo "Laguna M8 in-process replay telemetry PASS: $run_dir"
