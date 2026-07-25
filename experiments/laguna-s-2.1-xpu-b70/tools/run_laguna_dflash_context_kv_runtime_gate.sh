#!/usr/bin/env bash
# One-shot, non-timing TP4 selector-off/on DFlash context-KV runtime gate.
set -euo pipefail
set -f
umask 077
export PYTHONDONTWRITEBYTECODE=1

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
readonly repo=/home/steve/llm-optimizations
readonly vllm=/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725
readonly kernels=/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly tools="$repo/experiments/laguna-s-2.1-xpu-b70/tools"
readonly nvme_paths="$tools/laguna_nvme_paths.sh"
# shellcheck source=laguna_nvme_paths.sh
source "$nvme_paths"
readonly shell_path="$(realpath -e -- "$0")"
readonly driver="$tools/run_laguna_dflash_context_kv_runtime_arm.py"
readonly analyzer="$tools/analyze_laguna_dflash_context_kv_runtime_gate.py"
readonly consumer="$tools/create_laguna_dflash_context_kv_runtime_consumption.py"
readonly raw_analyzer="$tools/analyze_laguna_m8_actual_offline_gate.py"
readonly idle_wrapper="$tools/capture_laguna_m8_idle_snapshot.py"
readonly prereg="$repo/experiments/laguna-s-2.1-xpu-b70/notes/2026-07-25-dflash-context-kv-tp4-runtime-preregistration.md"
readonly suite="$repo/experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
readonly teacher="$LAGUNA_NVME_RUN_ROOT/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json"
readonly candidate_source="$vllm/vllm/model_executor/models/laguna_dflash.py"
readonly candidate_worker_source="$vllm/vllm/v1/worker/xpu_worker.py"
readonly root="${1:?usage: run_laguna_dflash_context_kv_runtime_gate.sh FRESH_NVME_ROOT}"
readonly expected_vllm=7c38a20229b7bcd0f149e3e9a6b6b5493c3bd85b
readonly expected_kernels=4772f727590c51b72add79350b913d098cf67872
readonly expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
readonly expected_teacher=d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1
readonly expected_candidate_source=4439472403047988f9f6d2022656d071f01753216c2afc119397e803aa1b1b0b
readonly expected_candidate_worker_source=8b0c1519bdab675d100b231b68d87e1b39fa54272adb0874895187ef2b2ffa2a
readonly expected_raw_analyzer=43526f74042d221b75895dc4760bf6664c32a51b247d317c13bcc941ce3a46fa
readonly authorization_dir=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations
readonly rpc_control="$LAGUNA_NVME_TMP_ROOT/dckvr-a"
readonly rpc_candidate="$LAGUNA_NVME_TMP_ROOT/dckvr-b"
active_pid=""
active_rpc=""
active_arm=""

die() {
  echo "Laguna DFlash context-KV runtime gate: $*" >&2
  exit 2
}

check_hash() {
  local path="$1" expected="$2" actual
  actual="$(sha256sum -- "$path" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || die "SHA256 drift: $path ($actual)"
}

assert_no_workers() {
  local report="$1"
  "$python" - "$report" <<'PY'
import os
import sys
from pathlib import Path

report = Path(sys.argv[1])
ancestors = set()
pid = os.getpid()
while pid > 1 and pid not in ancestors:
    ancestors.add(pid)
    try:
        pid = int(Path(f"/proc/{pid}/stat").read_text().split()[3])
    except (OSError, ValueError, IndexError):
        break

matches = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) in ancestors:
        continue
    try:
        argv = [
            item.decode("utf-8", "replace")
            for item in (proc / "cmdline").read_bytes().split(b"\0")
            if item
        ]
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
        item.startswith(("VLLM::EngineCore", "VLLM::Worker")) for item in argv
    )
    torchrun = basename == "torchrun" or (
        len(argv) >= 3
        and basename.startswith("python")
        and argv[1:3] == ["-m", "torch.distributed.run"]
    )
    if vllm_serve or vllm_worker or torchrun:
        matches.append(f"{proc.name}\t{comm}\t{' '.join(argv)}")

flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
flags |= getattr(os, "O_NOFOLLOW", 0)
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

active_group_alive() {
  [[ -n "$active_pid" ]] &&
    (kill -0 "$active_pid" 2>/dev/null || kill -0 -- "-$active_pid" 2>/dev/null)
}

stop_active() {
  local signal attempts
  [[ -n "$active_pid" ]] || return 0
  for signal in INT TERM KILL; do
    active_group_alive || break
    kill "-$signal" -- "-$active_pid" 2>/dev/null || true
    kill "-$signal" "$active_pid" 2>/dev/null || true
    case "$signal" in
      INT) attempts=30 ;;
      TERM) attempts=15 ;;
      KILL) attempts=10 ;;
    esac
    for _ in $(seq 1 "$attempts"); do
      active_group_alive || break
      sleep 1
    done
  done
  wait "$active_pid" 2>/dev/null || true
  active_group_alive && return 1
  active_pid=""
}

archive_rpc() {
  [[ -n "$active_rpc" && -d "$active_rpc" && -n "$active_arm" ]] || return 0
  [[ ! -e "$active_arm/rpc-after-stop" &&
     ! -L "$active_arm/rpc-after-stop" ]] ||
    return 1
  mv -- "$active_rpc" "$active_arm/rpc-after-stop" || return 1
  active_rpc=""
}

seal_outputs() {
  [[ -d "$root" ]] && chmod -R a-w -- "$root" || true
}

cleanup() {
  local status=$? stop_status=0 worker_status=0 idle_status=0 rpc_archive_status=0
  trap - EXIT INT TERM
  set +e
  stop_active || stop_status=1
  archive_rpc || rpc_archive_status=1
  if [[ -d "$root" && ! -e "$root/failure-workers.txt" ]]; then
    assert_no_workers "$root/failure-workers.txt" || worker_status=1
  else
    worker_status=1
  fi
  if [[ -d "$root" && ! -e "$root/failure-post-idle.json" ]]; then
    "$python" "$idle_wrapper" --output "$root/failure-post-idle.json" ||
      idle_status=1
  fi
  if [[ -d "$root" ]]; then
    printf 'original_status=%s\nstop_status=%s\nrpc_archive_status=%s\nworker_status=%s\nidle_status=%s\n' \
      "$status" "$stop_status" "$rpc_archive_status" "$worker_status" \
      "$idle_status" \
      >"$root/failure-cleanup-status.txt"
    find "$root" -type f ! -name failure-manifest.sha256 -print0 |
      sort -z | xargs -0 sha256sum >"$root/failure-manifest.sha256"
    sync -f "$root/failure-manifest.sha256"
  fi
  seal_outputs
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ "$0" == "$shell_path" && ! -L "$0" ]] ||
  die "runner must be invoked by its absolute non-symlink path"
[[ "$root" == "$LAGUNA_NVME_RUN_ROOT"/* ]] ||
  die "run root must be below the internal-NVMe Laguna run root"
[[ "$(realpath -m -- "$root")" == "$root" && ! -e "$root" && ! -L "$root" ]] ||
  die "run root must be fresh and canonical"

ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] ||
  die "refusing inherited runtime variables: $ambient_sensitive"
for path in \
  "$vllm" "$kernels" "$driver" "$analyzer" "$consumer" "$raw_analyzer" \
  "$idle_wrapper" "$nvme_paths" "$prereg" "$suite" "$teacher" \
  "$candidate_source" "$candidate_worker_source"; do
  [[ -e "$path" ]] || die "required path missing: $path"
  [[ "$(realpath -e -- "$path")" != /media/* ]] ||
    die "active path resolves to external USB: $path"
done
[[ -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)" ]] ||
  die "main worktree is dirty"
[[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" &&
   -z "$(git -C "$vllm" status --porcelain=v1 --untracked-files=all)" ]] ||
  die "vLLM source identity drift"
[[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" &&
   -z "$(git -C "$kernels" status --porcelain=v1 --untracked-files=all)" ]] ||
  die "kernel source identity drift"
check_hash "$suite" "$expected_suite"
check_hash "$teacher" "$expected_teacher"
check_hash "$candidate_source" "$expected_candidate_source"
check_hash "$candidate_worker_source" "$expected_candidate_worker_source"
check_hash "$raw_analyzer" "$expected_raw_analyzer"
check_hash "$kernels/vllm_xpu_kernels/_C.abi3.so" \
  126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
check_hash "$kernels/vllm_xpu_kernels/_xpu_C.abi3.so" \
  f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
check_hash "$kernels/vllm_xpu_kernels/_moe_C.abi3.so" \
  6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b
check_hash "$kernels/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96

laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$root"
laguna_nvme_verify_model_contents
for rpc in "$rpc_control" "$rpc_candidate"; do
  [[ ! -e "$rpc" && ! -L "$rpc" ]] || die "refusing reused RPC path: $rpc"
done

laguna_nvme_prepare_run_dir "$root"
chmod 700 -- "$root"
assert_no_workers "$root/pre-workers.txt" ||
  die "existing vLLM or torchrun workers block the gate"
for treatment in control candidate; do
  mkdir -p -- "$root/$treatment"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
  mkdir --mode=700 -- "$root/$treatment/dflash-lifecycle"
  chmod -R 700 -- "$root/$treatment"
done

/usr/bin/timeout --foreground --signal=TERM --kill-after=2s 20s \
  /usr/bin/env -i PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/xpu-smi discovery -j >"$root/device-discovery.json" ||
  die "four-card discovery failed before packet consumption"
"$python" "$idle_wrapper" --output "$root/pre-idle.json" ||
  die "devices are not strictly idle before packet consumption"

readonly main_commit="$(git -C "$repo" rev-parse HEAD)"
{
  printf 'schema=laguna-dflash-context-kv-runtime-campaign-v1\n'
  printf 'purpose=two-arm TP4 integration exactness; timing=false; benchmark=false; submission=false\n'
  printf 'main=%s\nvllm=%s\nkernels=%s\n' \
    "$main_commit" "$expected_vllm" "$expected_kernels"
  printf 'order=control,candidate\nsole_treatment=VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE\n'
  printf 'calls_per_arm=1\nmax_tokens=32\nwarmups=0\nretries=0\n'
  sha256sum -- \
    "$shell_path" "$driver" "$analyzer" "$consumer" "$raw_analyzer" \
    "$idle_wrapper" "$nvme_paths" "$prereg" "$suite" "$teacher" \
    "$candidate_source" "$candidate_worker_source"
} >"$root/identity.txt"
sync -f "$root/identity.txt"
readonly packet_sha256="$(sha256sum -- "$root/identity.txt" | awk '{print $1}')"
mkdir -p -- "$authorization_dir"
chmod 700 -- "$authorization_dir"
readonly consumption_marker="$authorization_dir/laguna-dflash-context-kv-runtime-${main_commit}-${packet_sha256}.consumed.json"
"$python" "$consumer" \
  --marker "$consumption_marker" \
  --run-root "$root" \
  --main-commit "$main_commit" \
  --packet-sha256 "$packet_sha256" \
  >"$root/consumption-creator.stdout" ||
  die "this exact committed runtime packet has already been consumed"

run_arm() {
  local treatment="$1" selector="$2" rpc="$3"
  local arm="$root/$treatment" status
  [[ ! -e "$rpc" && ! -L "$rpc" ]] ||
    die "refusing reused RPC path before $treatment: $rpc"
  mkdir --mode=700 -- "$rpc"
  active_rpc="$rpc"
  active_arm="$arm"
  assert_no_workers "$arm/pre-workers.txt" ||
    die "existing worker blocks $treatment"
  "$python" "$idle_wrapper" --output "$arm/pre-idle.json" ||
    die "devices are not idle before $treatment"

  setsid /usr/bin/timeout --foreground --preserve-status --signal=TERM \
    --kill-after=30s 2400s \
    /usr/bin/env -i \
    PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    HOME="$arm/private-home" TMP="$arm/private-tmp" TEMP="$arm/private-tmp" \
    TMPDIR="$arm/private-tmp" HF_HOME="$arm/private-cache/hf" \
    HF_HUB_CACHE="$arm/private-cache/hf/hub" \
    TRANSFORMERS_CACHE="$arm/private-cache/hf/transformers" \
    VLLM_CACHE_ROOT="$arm/private-cache/vllm" \
    TORCHINDUCTOR_CACHE_DIR="$arm/private-cache/torchinductor" \
    TRITON_CACHE_DIR="$arm/private-cache/triton" \
    SYCL_CACHE_DIR="$arm/private-cache/sycl" \
    NUMBA_CACHE_DIR="$arm/private-cache/numba" \
    PYTHONPYCACHEPREFIX="$arm/private-cache/pycache" \
    XDG_CACHE_HOME="$arm/private-cache" \
    XDG_CONFIG_HOME="$arm/private-xdg/config" \
    XDG_DATA_HOME="$arm/private-xdg/data" \
    XDG_STATE_HOME="$arm/private-xdg/state" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    PYTHONHASHSEED=0 PYTHONPATH="$tools:$vllm:$kernels" \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 \
    VLLM_RPC_BASE_PATH="$rpc" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    LD_PRELOAD= \
    ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 \
    CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 \
    CCL_KVS_IFACE=eno1 TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
    LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
    VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 \
    VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 \
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 \
    VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 \
    VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1 \
    VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1 \
    VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
    VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 \
    VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 \
    VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 \
    VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 \
    VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 \
    VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 \
    VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 \
    VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 \
    VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 \
    VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 \
    VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 \
    VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 \
    VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 \
    VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 \
    VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 \
    VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 \
    LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7 \
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1 \
    VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=0 \
    VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1 \
    VLLM_USE_BREAKABLE_CUDAGRAPH=1 XPU_GRAPH=1 \
    VLLM_XPU_ENABLE_XPU_GRAPH=1 \
    VLLM_XPU_LAGUNA_M8_EVIDENCE=1 \
    VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM=segmented-graph \
    VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT="$arm/evidence" \
    VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE="$selector" \
    VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_RUNTIME_TRACE=1 \
    VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_RUNTIME_TRACE_ROOT="$arm/dflash-lifecycle" \
    "$python" "$driver" \
      --treatment "$treatment" \
      --out "$arm/driver.json" \
      --evidence-dir "$arm/evidence" \
      --trace-dir "$arm/dflash-lifecycle" \
      --rpc-dir "$rpc" \
      >"$arm/driver.stdout" 2>"$arm/driver.stderr" &
  active_pid="$!"
  set +e
  wait "$active_pid"
  status=$?
  set -e
  if (( status != 0 )); then
    stop_active || true
    die "$treatment arm failed with status $status"
  fi
  if ! assert_no_workers "$arm/post-workers.txt"; then
    stop_active || true
    die "worker survived $treatment"
  fi
  active_pid=""
  "$python" "$idle_wrapper" --output "$arm/post-idle.json" ||
    die "devices are not idle after $treatment"
  printf 'status=0\nworker_status=0\nidle_status=0\n' \
    >"$arm/cleanup-status.txt"
  archive_rpc
  active_arm=""
}

run_arm control 0 "$rpc_control"
run_arm candidate 1 "$rpc_candidate"

assert_no_workers "$root/final-workers.txt" ||
  die "worker survived the two-arm campaign"
"$python" "$idle_wrapper" --output "$root/final-idle.json" ||
  die "devices are not idle before analysis"
find "$root" -type f \
  ! -path '*/private-home/*' \
  ! -path '*/private-tmp/*' \
  ! -path '*/private-cache/*' \
  ! -path '*/private-xdg/*' \
  ! -path '*/rpc-after-stop/*' \
  ! -name evidence-manifest.sha256 \
  ! -name analysis.json \
  ! -name analyzer.stdout \
  ! -name analyzer.stderr \
  -print0 |
  sort -z | xargs -0 sha256sum >"$root/evidence-manifest.sha256"
sync -f "$root/evidence-manifest.sha256"
"$python" "$analyzer" --root "$root" --out "$root/analysis.json" \
  >"$root/analyzer.stdout" 2>"$root/analyzer.stderr"
find "$root" -type f ! -name final-manifest.sha256 -print0 |
  sort -z | xargs -0 sha256sum >"$root/final-manifest.sha256"
sync -f "$root/final-manifest.sha256"
chmod -R a-w -- "$root"
trap - EXIT
echo "Laguna DFlash context-KV TP4 runtime exactness PASS: $root"
