#!/usr/bin/env bash
# Private-NVMe, offline, non-benchmark A/B/C raw-byte gate for Laguna M=8.
set -euo pipefail
umask 077
readonly frozen_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

run_dir="${1:?usage: run_laguna_m8_actual_offline_gate.sh RUN_DIR}"
readonly segmented_root=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
readonly venv_python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
readonly draft_revision=5e07c246915c86dc6920fead03d019989224f2ba
readonly record_vllm=8936aac144929190c1e53f8b8624ca397ce16f5b
readonly record_kernels=b6076ce1249ffee0e30bee528f4cd15c3bffb234
readonly frozen_segmented_vllm=e25867aa698f82cbf2fb835e26807078674acebc
readonly frozen_kernel_head=4772f727590c51b72add79350b913d098cf67872
readonly rpc_dir_incumbent="$LAGUNA_NVME_TMP_ROOT/m8p7-a"
readonly rpc_dir_segmented_eager="$LAGUNA_NVME_TMP_ROOT/m8p7-b"
readonly rpc_dir_segmented_graph="$LAGUNA_NVME_TMP_ROOT/m8p7-c"
readonly zmq_uuid_name_length=36
readonly zmq_conservative_path_max=100
readonly frozen_kernel_binaries=$'126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2  vllm_xpu_kernels/_C.abi3.so\nf5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8  vllm_xpu_kernels/_xpu_C.abi3.so\n6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b  vllm_xpu_kernels/_moe_C.abi3.so\nfc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96  vllm_xpu_kernels/libgrouped_gemm_xe_2.so'
readonly frozen_runtime_binaries=$'ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3  /home/steve/.venvs/deepseek-v4-xpu/lib/libccl.so.1\n0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f  /home/steve/.venvs/deepseek-v4-xpu/lib/libsycl.so.8\n26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a  /usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1\n0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0  /lib/x86_64-linux-gnu/libze_loader.so.1'
declare -a created_paths=()

die() { echo "Laguna M8 actual offline gate: $*" >&2; exit 2; }
seal_outputs() {
  local path
  for path in "${created_paths[@]}"; do
    [[ -d "$path" ]] && chmod -R a-w -- "$path" || true
  done
}
trap 'rc=$?; seal_outputs; exit "$rc"' EXIT
assert_no_workers() {
  local report="$1"
  "$venv_python" - "$report" <<'PY'
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
        argv = (proc / "cmdline").read_bytes().split(b"\0")
        argv = [item.decode("utf-8", "replace") for item in argv if item]
        comm = (proc / "comm").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        continue
    if not argv:
        continue
    basename = Path(argv[0]).name
    vllm_serve = any(
        argv[index] == "vllm" and argv[index + 1] == "serve"
        for index in range(len(argv) - 1)
    )
    vllm_worker = comm.startswith("VLLM::") or any(
        item.startswith("VLLM::EngineCore") or item.startswith("VLLM::Worker")
        for item in argv
    )
    torchrun = basename == "torchrun" or (
        len(argv) >= 3
        and Path(argv[0]).name.startswith("python")
        and argv[1:3] == ["-m", "torch.distributed.run"]
    )
    if vllm_serve or vllm_worker or torchrun:
        matches.append(f"{proc.name}\t{comm}\t{' '.join(argv)}")

flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
descriptor = os.open(report, flags, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
    handle.write("\n".join(matches))
    if matches:
        handle.write("\n")
if matches:
    print("\n".join(matches), file=sys.stderr)
    raise SystemExit(1)
PY
}
capture_idle() {
  local output="$1"
  "$venv_python" "$script_dir/capture_laguna_m8_idle_snapshot.py" \
    --output "$output"
}

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "RUN_DIR must be below fixed NVMe run root"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "RUN_DIR must be canonical"
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
for path in "$segmented_root" "$kernel_root" "$venv_python"; do
  [[ -e "$path" ]] || die "required path does not exist: $path"
  case "$(realpath -e -- "$path")" in /media/*) die "external USB path forbidden: $path";; esac
done
[[ -z "$(git -C "$segmented_root" status --short)" ]] || die "segmented recorder worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
segmented_expected_commit="$frozen_segmented_vllm"
[[ "$(git -C "$segmented_root" rev-parse HEAD)" == "$segmented_expected_commit" ]] || die "segmented vLLM HEAD does not match reviewed recorder commit"
git -C "$segmented_root" merge-base --is-ancestor "$record_vllm" "$segmented_expected_commit" || die "reviewed recorder commit is not an approved-record descendant"
[[ "$(git -C "$kernel_root" rev-parse HEAD)" == "$frozen_kernel_head" ]] || die "kernel worktree is not frozen mwidth-mhc descendant"
git -C "$kernel_root" merge-base --is-ancestor "$record_kernels" "$frozen_kernel_head" || die "frozen kernel head is not an approved-record descendant"
while read -r expected_hash relative; do
  [[ "$(sha256sum "$kernel_root/$relative" | awk '{print $1}')" == "$expected_hash" ]] || die "frozen kernel binary differs: $relative"
done <<< "$frozen_kernel_binaries"
while read -r expected_hash absolute; do
  [[ "$(sha256sum "$absolute" | awk '{print $1}')" == "$expected_hash" ]] || die "frozen runtime binary differs: $absolute"
done <<< "$frozen_runtime_binaries"
rg -q --fixed-strings 'VLLM_XPU_LAGUNA_M8_EVIDENCE' "$segmented_root/vllm/compilation/laguna_m8_evidence.py" || die "reviewed runtime lacks evidence opt-in"
rg -q --fixed-strings 'laguna-m8-raw-evidence-v2' "$segmented_root/vllm/compilation/laguna_m8_evidence.py" || die "reviewed runtime lacks raw evidence format"
rg -q --fixed-strings 'LAGUNA_M8_RAW_EVIDENCE_V2' "$segmented_root/vllm/compilation/laguna_m8_evidence.py" || die "reviewed runtime lacks raw evidence marker"

ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited benchmark/runtime variables: $ambient_sensitive"
created_paths+=("$run_dir")
laguna_nvme_prepare_run_dir "$run_dir"
chmod 700 -- "$run_dir"
for rpc_dir in \
  "$rpc_dir_incumbent" "$rpc_dir_segmented_eager" "$rpc_dir_segmented_graph"; do
  [[ "$(realpath -m -- "$rpc_dir")" == "$rpc_dir" ]] \
    || die "RPC base must be canonical: $rpc_dir"
  [[ "$rpc_dir" == "$LAGUNA_NVME_TMP_ROOT"/m8p7-? ]] \
    || die "RPC base differs from the frozen short layout: $rpc_dir"
  [[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] \
    || die "refusing to reuse RPC base: $rpc_dir"
  (( ${#rpc_dir} + 1 + zmq_uuid_name_length <= zmq_conservative_path_max )) \
    || die "RPC base leaves insufficient Unix-socket path headroom: $rpc_dir"
  created_paths+=("$rpc_dir")
  mkdir --mode=700 -- "$rpc_dir"
  laguna_nvme_assert_fixed_path "$rpc_dir"
  [[ "$(stat -c '%a' -- "$rpc_dir")" == 700 ]] \
    || die "RPC base is not owner-private mode 0700: $rpc_dir"
done
assert_no_workers "$run_dir/pre-arm-workers.txt" \
  || die "existing vLLM/torchrun worker blocks a fresh offline arm"
laguna_nvme_verify_model_contents
capture_idle "$run_dir/pre-arm-idle.json" || die "strict pre-arm XPU idle proof failed"
for arm in incumbent-eager segmented-eager segmented-graph; do
  mkdir -p "$run_dir/$arm"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
  chmod -R 700 -- "$run_dir/$arm"
done

driver="$script_dir/run_laguna_m8_actual_offline.py"
analyzer="$script_dir/analyze_laguna_m8_actual_offline_gate.py"
idle_wrapper="$script_dir/capture_laguna_m8_idle_snapshot.py"
[[ -f "$driver" && -f "$analyzer" && -f "$idle_wrapper" ]] || die "gate scripts missing"
segmented_commit="$(git -C "$segmented_root" rev-parse HEAD)"
{
  printf 'purpose=offline correctness component gate; not a benchmark or submission\n'
  printf 'record_vllm=%s\nrecord_kernels=%s\nkernel_descendant=%s\nall_arms_vllm=%s\n' "$record_vllm" "$record_kernels" "$frozen_kernel_head" "$segmented_commit"
  printf '%s\n' "$frozen_kernel_binaries"
  printf '%s\n' "$frozen_runtime_binaries"
  printf 'raw_evidence_env=VLLM_XPU_LAGUNA_M8_EVIDENCE,VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM,VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT\n'
  printf 'arms=incumbent-eager(segmentation-off),segmented-eager,segmented-graph\n'
  printf 'rpc_incumbent=%s\nrpc_segmented_eager=%s\nrpc_segmented_graph=%s\n' \
    "$rpc_dir_incumbent" "$rpc_dir_segmented_eager" "$rpc_dir_segmented_graph"
  printf 'rpc_uuid_socket_path_bytes=100; conservative_max=100; pyzmq_platform_max=107\n'
  printf 'execution=A/B approved enforce-eager with no compilation argument; C mode:NONE PIECEWISE capture_sizes:[8]\n'
  printf 'timing_and_pti=not_run\n'
  printf 'stop_rules=any low-level manifest/file/byte mismatch, request/event/config drift, process failure, external path, identity drift, or extra generation fails closed\n'
  sha256sum "$driver" "$analyzer" "$idle_wrapper" "$0" "$script_dir/laguna_nvme_paths.sh"
} > "$run_dir/identity.txt"

run_arm() {
  local arm="$1" graph=0 arm_dir="$run_dir/$1" rpc_dir arm_status post_status=0
  case "$arm" in
    incumbent-eager) rpc_dir="$rpc_dir_incumbent" ;;
    segmented-eager) rpc_dir="$rpc_dir_segmented_eager" ;;
    segmented-graph)
      graph=1
      rpc_dir="$rpc_dir_segmented_graph"
      ;;
    *) die "unknown arm: $arm" ;;
  esac
  assert_no_workers "$arm_dir/pre-workers.txt" \
    || die "existing worker blocks arm $arm"
  capture_idle "$arm_dir/pre-idle.json" \
    || die "strict pre-arm idle proof failed for $arm"
  set +e
  /usr/bin/timeout --preserve-status --signal=TERM --kill-after=30s 1800s /usr/bin/env -i \
    PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    HOME="$arm_dir/private-home" TMP="$arm_dir/private-tmp" TEMP="$arm_dir/private-tmp" TMPDIR="$arm_dir/private-tmp" \
    HF_HOME="$arm_dir/private-cache/hf" HF_HUB_CACHE="$arm_dir/private-cache/hf/hub" TRANSFORMERS_CACHE="$arm_dir/private-cache/hf/transformers" \
    VLLM_CACHE_ROOT="$arm_dir/private-cache/vllm" TORCHINDUCTOR_CACHE_DIR="$arm_dir/private-cache/torchinductor" TRITON_CACHE_DIR="$arm_dir/private-cache/triton" SYCL_CACHE_DIR="$arm_dir/private-cache/sycl" NUMBA_CACHE_DIR="$arm_dir/private-cache/numba" PYTHONPYCACHEPREFIX="$arm_dir/private-cache/pycache" \
    XDG_CACHE_HOME="$arm_dir/private-cache" XDG_CONFIG_HOME="$arm_dir/private-xdg/config" XDG_DATA_HOME="$arm_dir/private-xdg/data" XDG_STATE_HOME="$arm_dir/private-xdg/state" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 PYTHONPATH="$script_dir:$segmented_root:$kernel_root" \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD= \
    ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
    LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
    VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 \
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1 VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1 VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
    VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 \
    VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 \
    VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7 \
    VLLM_XPU_LAGUNA_M8_EVIDENCE=1 VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM="$arm" VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT="$arm_dir/evidence" \
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
    "$venv_python" "$driver" --arm "$arm" --out "$arm_dir/driver.json" --evidence-dir "$arm_dir/evidence" --rpc-dir "$rpc_dir" --model "$LAGUNA_NVME_TARGET_ROOT" --draft-model "$LAGUNA_NVME_DRAFT_ROOT" --revision "$target_revision" --draft-revision "$draft_revision" --expected-vllm-commit "$segmented_commit" >"$arm_dir/stdout.log" 2>"$arm_dir/stderr.log"
  arm_status=$?
  set -e
  assert_no_workers "$arm_dir/post-workers.txt" || post_status=1
  capture_idle "$arm_dir/post-idle.json" || post_status=1
  (( arm_status == 0 )) || die "arm $arm failed with status $arm_status"
  (( post_status == 0 )) || die "arm $arm left workers or non-idle XPUs"
}

run_arm incumbent-eager
run_arm segmented-eager
run_arm segmented-graph
"$venv_python" "$analyzer" --run-dir "$run_dir" --out "$run_dir/analysis.json"
echo "Laguna M8 offline raw-byte A/B/C gate PASS: $run_dir"
