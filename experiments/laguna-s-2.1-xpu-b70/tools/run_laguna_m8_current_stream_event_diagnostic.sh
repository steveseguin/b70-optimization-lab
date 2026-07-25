#!/usr/bin/env bash
# Two-arm, one-shot Laguna current-stream event diagnostic; never benchmark evidence.
set -euo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

run_dir="${1:?usage: run_laguna_m8_current_stream_event_diagnostic.sh RUN_DIR}"
(( $# == 1 )) || { echo "exactly one run directory is required" >&2; exit 2; }
readonly repo_root=/home/steve/llm-optimizations
readonly vllm_root=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727
readonly python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly driver="$script_dir/run_laguna_m8_current_stream_event_arm.py"
readonly analyzer="$script_dir/analyze_laguna_m8_current_stream_event.py"
readonly contract="$script_dir/laguna_m8_current_stream_event_contract.py"
readonly idle="$script_dir/capture_laguna_m8_idle_snapshot.py"
readonly expected_vllm=fcc2506f7da3a9fd142928af9275d25b9687342a
readonly expected_kernels=4772f727590c51b72add79350b913d098cf67872
readonly record_vllm=ef334233deabeaeedb607056a2db1c90edb3887c
declare -a created=()
active_pg=""

die() { echo "Laguna current-stream event diagnostic: $*" >&2; exit 2; }

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

seal() { local path; for path in "${created[@]}"; do [[ -e "$path" ]] && chmod -R a-w -- "$path" || true; done; }
trap 'rc=$?; cleanup_active_pg; seal; exit "$rc"' EXIT

assert_no_workers() {
  "$python" - "$1" <<'PY'
import os, sys
from pathlib import Path
report = Path(sys.argv[1]); ancestors=set(); pid=os.getpid()
while pid > 1 and pid not in ancestors:
    ancestors.add(pid)
    try: pid=int(Path(f"/proc/{pid}/stat").read_text().split()[3])
    except (OSError, ValueError, IndexError): break
rows=[]
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit() or int(proc.name) in ancestors: continue
    try:
        argv=[x.decode("utf-8", "replace") for x in (proc / "cmdline").read_bytes().split(b"\0") if x]
        comm=(proc / "comm").read_text().strip()
    except (OSError, UnicodeError): continue
    if not argv: continue
    serve=any(argv[i] == "vllm" and argv[i+1] == "serve" for i in range(len(argv)-1))
    worker=comm.startswith("VLLM::") or any(x.startswith(("VLLM::EngineCore", "VLLM::Worker")) for x in argv)
    torchrun=Path(argv[0]).name == "torchrun" or (len(argv)>=3 and Path(argv[0]).name.startswith("python") and argv[1:3] == ["-m", "torch.distributed.run"])
    if serve or worker or torchrun: rows.append(f"{proc.name}\t{comm}\t{' '.join(argv)}")
fd=os.open(report, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as h: h.write("\n".join(rows) + ("\n" if rows else ""))
if rows:
    print("\n".join(rows), file=sys.stderr); raise SystemExit(1)
PY
}

capture_idle() { "$python" "$idle" --output "$1"; }
check_hash() { [[ "$(sha256sum -- "$1" | awk '{print $1}')" == "$2" ]] || die "SHA256 mismatch for $1"; }

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "run root must be on internal NVMe"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run root must be canonical"
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
run_tag="$(printf '%s' "$run_dir" | sha256sum | cut -c1-12)"
ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited runtime variables: $ambient_sensitive"
for path in "$repo_root" "$vllm_root" "$kernel_root" "$python" "$driver" "$analyzer" "$contract" "$idle" "$script_dir/laguna_nvme_paths.sh"; do
  [[ -e "$path" && "$(realpath -e -- "$path")" != /media/* ]] || die "missing or external required path: $path"
done
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
[[ "$(git -C "$vllm_root" rev-parse HEAD)" == "$expected_vllm" ]] || die "vLLM commit drift"
[[ "$(git -C "$kernel_root" rev-parse HEAD)" == "$expected_kernels" ]] || die "kernel commit drift"
git -C "$vllm_root" merge-base --is-ancestor "$record_vllm" "$expected_vllm" \
  || die "event runtime is not an approved-record descendant"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" 126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" 6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b
check_hash "$kernel_root/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" e6faed930bbcd7a366cc55281b99e1a8d7016a8db40ab10015d78f72937c8e64
check_hash "$kernel_root/vllm_xpu_kernels/libattn_kernels_xe_2.so" 680d486970eb58dc63f0b7ef41e028e2bb4b5a630a2987c96f8609d46a00e161
check_hash "$kernel_root/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so" cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_default.so" 982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c
check_hash "$kernel_root/vllm_xpu_kernels/libmhc_kernels_xe_2.so" f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f
check_hash "$kernel_root/vllm_xpu_kernels/libmqa_logits_kernels_xe_2.so" 58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb

created+=("$run_dir")
laguna_nvme_prepare_run_dir "$run_dir"; chmod 700 -- "$run_dir"
for arm in q1 graph-event; do
  arm_dir="$run_dir/$arm"; suffix="${arm:0:1}"; rpc_dir="$LAGUNA_NVME_TMP_ROOT/e${run_tag:0:8}${suffix}"
  (( ${#rpc_dir} + 1 + 36 <= 107 )) || die "projected ZMQ IPC path is too long"
  [[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "reused RPC path: $rpc_dir"
  mkdir --mode=700 -- "$rpc_dir"; created+=("$rpc_dir")
  mkdir -p -- "$arm_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
  chmod -R 700 -- "$arm_dir"
done
event_root="$run_dir/graph-event/current-stream-event-profile"
mkdir --mode=700 -- "$event_root"
[[ -z "$(find "$event_root" -mindepth 1 -maxdepth 1 -print -quit)" ]] || die "event root was not empty"

assert_no_workers "$run_dir/pre-workers.txt" || die "existing vLLM/torchrun worker blocks diagnostic"
capture_idle "$run_dir/pre-idle.json" || die "strict pre-diagnostic device idle proof failed"
laguna_nvme_verify_model_contents
{
  printf 'schema=laguna-m8-current-stream-event-controller-v1\n'
  printf 'purpose=one-shot rank-local current-stream event diagnostic; never benchmark or submission evidence\n'
  printf 'arms=q1,graph-event; one_generation_per_fresh_process=true; completion_tokens_per_arm=272\n'
  printf 'main=%s\n' "$(git -C "$repo_root" rev-parse HEAD)"
  printf 'vllm=%s\nkernels=%s\nrun_tag=%s\n' "$expected_vllm" "$expected_kernels" "$run_tag"
  printf 'event_profile_root=%s\nexpected_rank_files=rank0.json,rank1.json,rank2.json,rank3.json\n' "$event_root"
  sha256sum "$0" "$driver" "$analyzer" "$contract" "$idle" "$script_dir/laguna_nvme_paths.sh" "$LAGUNA_NVME_LOCAL_MANIFEST"
  "$python" - <<'PY'
import platform, sys, torch
print(f"python_executable={sys.executable}")
print(f"python_version={sys.version}")
print(f"torch_version={torch.__version__}")
print(f"kernel={platform.release()}")
PY
} > "$run_dir/identity.txt"

run_arm() {
  local arm="$1" graph=0 arm_dir="$run_dir/$1" rpc_dir status post_status=0 survivors=0 attempt
  local -a event_env=() driver_args=()
  [[ "$arm" == graph-event ]] && graph=1
  rpc_dir="$LAGUNA_NVME_TMP_ROOT/e${run_tag:0:8}${arm:0:1}"
  driver_args=("$python" "$driver" --arm "$arm" --out "$arm_dir/driver.json")
  if (( graph )); then event_env=("VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT=$event_root"); driver_args+=(--event-root "$event_root"); fi
  assert_no_workers "$arm_dir/pre-workers.txt" || die "existing worker blocks $arm"
  capture_idle "$arm_dir/pre-idle.json" || die "strict pre-arm idle proof failed for $arm"
  set +e
  (
    cd -- "$arm_dir"
    exec setsid /usr/bin/timeout --preserve-status --signal=TERM --kill-after=30s 2400s /usr/bin/env -i \
      PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 HOME="$arm_dir/private-home" TMP="$arm_dir/private-tmp" TEMP="$arm_dir/private-tmp" TMPDIR="$arm_dir/private-tmp" \
      HF_HOME="$arm_dir/private-cache/hf" HF_HUB_CACHE="$arm_dir/private-cache/hf/hub" TRANSFORMERS_CACHE="$arm_dir/private-cache/hf/transformers" \
      VLLM_CACHE_ROOT="$arm_dir/private-cache/vllm" TORCHINDUCTOR_CACHE_DIR="$arm_dir/private-cache/torchinductor" TRITON_CACHE_DIR="$arm_dir/private-cache/triton" SYCL_CACHE_DIR="$arm_dir/private-cache/sycl" NUMBA_CACHE_DIR="$arm_dir/private-cache/numba" PYTHONPYCACHEPREFIX="$arm_dir/private-cache/pycache" \
      XDG_CACHE_HOME="$arm_dir/private-cache" XDG_CONFIG_HOME="$arm_dir/private-xdg/config" XDG_DATA_HOME="$arm_dir/private-xdg/data" XDG_STATE_HOME="$arm_dir/private-xdg/state" \
      PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 PYTHONPATH="$script_dir:$vllm_root:$kernel_root" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD= \
      ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
      LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
      VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2="$graph" VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE="$graph" VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE="$graph" VLLM_XPU_LAGUNA_M8_QKNORM_ROPE="$graph" VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7 VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=0 VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA="$graph" VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS=0 VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
      "${event_env[@]}" "${driver_args[@]}" >"$arm_dir/stdout.log" 2>"$arm_dir/stderr.log"
  ) &
  active_pg="$!"; wait "$active_pg"; status=$?; set -e
  for attempt in $(seq 1 10); do kill -0 -- "-$active_pg" 2>/dev/null || break; sleep 1; done
  if kill -0 -- "-$active_pg" 2>/dev/null; then survivors=1; cleanup_active_pg; fi
  active_pg=""
  assert_no_workers "$arm_dir/post-workers.txt" || post_status=1
  capture_idle "$arm_dir/post-idle.json" || post_status=1
  (( status == 0 )) || die "$arm arm failed with status $status"
  (( survivors == 0 )) || die "$arm arm left its process group alive"
  (( post_status == 0 )) || die "$arm arm left workers or non-idle XPUs"
  mv -- "$rpc_dir" "$arm_dir/rpc-after-stop"
}

run_arm q1
run_arm graph-event
assert_no_workers "$run_dir/post-workers.txt" || die "surviving worker after diagnostic"
capture_idle "$run_dir/post-idle.json" || die "strict post-diagnostic device idle proof failed"
"$python" - "$run_dir" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])

def identity(path: Path) -> dict[str, str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": str(path), "sha256": digest}

q1 = root / "q1" / "driver.json"
graph = root / "graph-event" / "driver.json"
graph_record = json.loads(graph.read_text(encoding="utf-8"))
profiles = graph_record.get("event_rank_files")
if not isinstance(profiles, dict) or set(profiles) != {"0", "1", "2", "3"}:
    raise SystemExit("graph arm did not bind four event profiles")
check_names = [
    "pre-workers.txt",
    "pre-idle.json",
    "q1/pre-workers.txt",
    "q1/pre-idle.json",
    "q1/post-workers.txt",
    "q1/post-idle.json",
    "graph-event/pre-workers.txt",
    "graph-event/pre-idle.json",
    "graph-event/post-workers.txt",
    "graph-event/post-idle.json",
    "post-workers.txt",
    "post-idle.json",
]
closure = {
    "schema": "laguna-m8-current-stream-event-closure-v1",
    "status": "complete",
    "diagnostic_only": True,
    "model_generation_count": 2,
    "network_access": False,
    "localmaxxing_submission_made": False,
    "identity": identity(root / "identity.txt"),
    "arms": {"q1": identity(q1), "graph-event": identity(graph)},
    "profiles": profiles,
    "checks": {name: identity(root / name) for name in check_names},
}
raw = (json.dumps(closure, sort_keys=True, separators=(",", ":")) + "\n").encode()
fd = os.open(
    root / "closure.json",
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
    0o600,
)
try:
    offset = 0
    while offset < len(raw):
        written = os.write(fd, raw[offset:])
        if written <= 0:
            raise RuntimeError("short closure write")
        offset += written
    os.fsync(fd)
finally:
    os.close(fd)
PY
"$python" "$analyzer" --run-dir "$run_dir" --out "$run_dir/analysis.json"
[[ "$(jq -r '.status' "$run_dir/analysis.json")" == "exact_event_profile_stop" ]] || die "unexpected analysis status"
printf 'status=exact_event_profile_stop\n' > "$run_dir/status.txt"
echo "Laguna current-stream event diagnostic complete: $run_dir"
