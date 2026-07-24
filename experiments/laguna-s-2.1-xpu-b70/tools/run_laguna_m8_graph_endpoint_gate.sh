#!/usr/bin/env bash
# Two-fresh-start endpoint correctness gate for the exact Laguna M8 graph stack.
set -euo pipefail
umask 077

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

run_dir="${1:?usage: run_laguna_m8_graph_endpoint_gate.sh RUN_DIR}"
readonly repo_root=/home/steve/llm-optimizations
readonly vllm_root=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
readonly venv_python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly serve_script="$script_dir/serve_laguna_m8_breakable_graph_nvme.sh"
readonly analyzer="$script_dir/analyze_laguna_m8_graph_endpoint.py"
readonly comparator="$script_dir/compare_exact_runs.py"
readonly idle_wrapper="$script_dir/capture_laguna_m8_idle_snapshot.py"
readonly benchmark="$repo_root/scripts/bench-openai-realistic-suite.py"
readonly suite="$repo_root/experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
readonly teacher="$LAGUNA_NVME_RUN_ROOT/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json"
readonly expected_vllm=0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca
readonly expected_kernels=4772f727590c51b72add79350b913d098cf67872
readonly record_vllm=8936aac144929190c1e53f8b8624ca397ce16f5b
readonly record_kernels=b6076ce1249ffee0e30bee528f4cd15c3bffb234
readonly expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
readonly expected_teacher=d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1
readonly expected_comparator=87ad4d57907a15afba221be42ea00e3a1975308d421e0edc13881dafe38e3db3
readonly expected_benchmark=40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a
readonly expected_target_config=9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
readonly expected_draft_config=6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
readonly expected_target_tree=0128e1ddc4954ade6b4ab7677376e3f3a95aaa02ffede3efdd314f3d4d766643
readonly expected_draft_tree=452f28ec2d80bcc33dc89e3581996dd6c1b706243097ea4b342d7f4ee08b08be
readonly rpc_a="$LAGUNA_NVME_TMP_ROOT/m8qb-a"
readonly rpc_b="$LAGUNA_NVME_TMP_ROOT/m8qb-b"
readonly compilation_json='{"mode":"NONE","cudagraph_mode":"PIECEWISE","cudagraph_capture_sizes":[8],"max_cudagraph_capture_size":8}'
declare -a created_paths=()
server_pid=""
active_leg_dir=""

die() {
  echo "Laguna M8 graph endpoint gate: $*" >&2
  exit 2
}

seal_outputs() {
  local path
  for path in "${created_paths[@]}"; do
    [[ -d "$path" ]] && chmod -R a-w -- "$path" || true
  done
}

service_alive() {
  [[ -n "$server_pid" ]] && (
    kill -0 "$server_pid" 2>/dev/null || kill -0 -- "-$server_pid" 2>/dev/null
  )
}

stop_service() {
  local signal attempts
  [[ -n "$server_pid" ]] || return 0
  for signal in INT TERM KILL; do
    service_alive || break
    kill "-$signal" -- "-$server_pid" 2>/dev/null || true
    kill "-$signal" "$server_pid" 2>/dev/null || true
    case "$signal" in
      INT) attempts=30 ;;
      TERM) attempts=15 ;;
      KILL) attempts=10 ;;
    esac
    for _ in $(seq 1 "$attempts"); do
      service_alive || break
      sleep 1
    done
  done
  wait "$server_pid" 2>/dev/null || true
  service_alive && return 1
  server_pid=""
}

finalize() {
  local status="$?"
  local stop_status=0 worker_status=0 idle_status=0
  trap - EXIT INT TERM
  set +e
  if [[ -n "$active_leg_dir" ]]; then
    stop_service || stop_status=1
    assert_no_workers "$active_leg_dir/failure-post-workers.txt" || worker_status=1
    capture_idle "$active_leg_dir/failure-post-idle.json" || idle_status=1
    printf 'original_status=%s\nstop_status=%s\nworker_status=%s\nidle_status=%s\n' \
      "$status" "$stop_status" "$worker_status" "$idle_status" \
      > "$active_leg_dir/failure-cleanup-status.txt"
  else
    stop_service
  fi
  seal_outputs
  exit "$status"
}
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

assert_no_workers() {
  local report="$1"
  "$venv_python" - "$report" <<'PY'
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
    vllm_serve = any(
        argv[index] == "vllm" and argv[index + 1] == "serve"
        for index in range(len(argv) - 1)
    )
    vllm_worker = comm.startswith("VLLM::") or any(
        item.startswith(("VLLM::EngineCore", "VLLM::Worker")) for item in argv
    )
    if vllm_serve or vllm_worker:
        matches.append(f"{proc.name}\t{comm}\t{' '.join(argv)}")
report.write_text("\n".join(matches) + ("\n" if matches else ""), encoding="utf-8")
if matches:
    print("\n".join(matches), file=sys.stderr)
    raise SystemExit(1)
PY
}

capture_idle() {
  "$venv_python" "$idle_wrapper" --output "$1"
}

check_hash() {
  local path="$1" expected="$2" actual
  actual="$(sha256sum -- "$path" | awk '{print $1}')"
  [[ "$actual" == "$expected" ]] || die "SHA256 mismatch for $path: $actual"
}

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "run root must be on fixed NVMe"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run root must be canonical"
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"

ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited runtime variables: $ambient_sensitive"

for path in \
  "$vllm_root" "$kernel_root" "$serve_script" "$analyzer" "$comparator" \
  "$idle_wrapper" "$benchmark" "$suite" "$teacher"; do
  [[ -e "$path" ]] || die "required path missing: $path"
  [[ "$(realpath -e -- "$path")" != /media/* ]] || die "active path is on external USB: $path"
done
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
[[ "$(git -C "$vllm_root" rev-parse HEAD)" == "$expected_vllm" ]] || die "vLLM commit drift"
[[ "$(git -C "$kernel_root" rev-parse HEAD)" == "$expected_kernels" ]] || die "kernel commit drift"
git -C "$vllm_root" merge-base --is-ancestor "$record_vllm" "$expected_vllm" \
  || die "graph runtime is not an approved-record descendant"
git -C "$kernel_root" merge-base --is-ancestor "$record_kernels" "$expected_kernels" \
  || die "kernel runtime is not an approved-record descendant"

check_hash "$suite" "$expected_suite"
check_hash "$teacher" "$expected_teacher"
check_hash "$comparator" "$expected_comparator"
check_hash "$benchmark" "$expected_benchmark"
check_hash "$LAGUNA_NVME_TARGET_ROOT/config.json" "$expected_target_config"
check_hash "$LAGUNA_NVME_DRAFT_ROOT/config.json" "$expected_draft_config"
check_hash \
  "$LAGUNA_NVME_TARGET_ROOT/.cache/huggingface/trees/4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb.json" \
  "$expected_target_tree"
check_hash \
  "$LAGUNA_NVME_DRAFT_ROOT/.cache/huggingface/trees/5e07c246915c86dc6920fead03d019989224f2ba.json" \
  "$expected_draft_tree"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" \
  126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" \
  f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" \
  6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96

created_paths+=("$run_dir")
laguna_nvme_prepare_run_dir "$run_dir"
chmod 700 -- "$run_dir"
for rpc_dir in "$rpc_a" "$rpc_b"; do
  [[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "refusing reused RPC path: $rpc_dir"
  mkdir --mode=700 -- "$rpc_dir"
  created_paths+=("$rpc_dir")
done
for leg in start-a start-b; do
  mkdir -p "$run_dir/$leg"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
  chmod -R 700 -- "$run_dir/$leg"
done

assert_no_workers "$run_dir/pre-workers.txt" || die "existing vLLM worker blocks gate"
! ss -H -ltn 'sport = :18080' | grep -q . || die "port 18080 already has a listener"
capture_idle "$run_dir/pre-idle.json" || die "devices are not strictly idle"
laguna_nvme_verify_model_contents

{
  printf 'purpose=two-fresh-start endpoint correctness; no timing or record claim\n'
  printf 'vllm=%s\nkernels=%s\n' "$expected_vllm" "$expected_kernels"
  printf 'execution=%s\n' "$compilation_json"
  printf 'teacher=%s\nsuite=%s\n' "$teacher" "$suite"
  sha256sum "$0" "$serve_script" "$analyzer" "$comparator" "$benchmark" "$suite" "$teacher"
} > "$run_dir/identity.txt"

run_leg() {
  local leg="$1" rpc_dir="$2" leg_dir="$run_dir/$1"
  local stop_status=0 worker_status=0 idle_status=0 ready=0

  assert_no_workers "$leg_dir/pre-workers.txt" || die "existing worker blocks $leg"
  capture_idle "$leg_dir/pre-idle.json" || die "devices are not idle before $leg"
  active_leg_dir="$leg_dir"

  "$venv_python" - "$leg_dir/identity.json" "$expected_vllm" "$expected_kernels" <<'PY'
import json
import sys
from pathlib import Path

out, vllm_commit, kernel_commit = sys.argv[1:]
identity = {
    "schema": "laguna-m8-graph-endpoint-leg-v1",
    "claim": "endpoint correctness only",
    "vllm_commit": vllm_commit,
    "kernel_commit": kernel_commit,
    "model": "/mnt/fast-ai/llm-models/laguna-s-2.1/int4",
    "model_revision": "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb",
    "draft_model": "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4",
    "draft_revision": "5e07c246915c86dc6920fead03d019989224f2ba",
    "execution": {
        "VLLM_USE_AOT_COMPILE": "0",
        "VLLM_USE_BREAKABLE_CUDAGRAPH": "1",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1",
        "XPU_GRAPH": "1",
        "compilation": {
            "mode": "NONE",
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [8],
            "max_cudagraph_capture_size": 8,
        },
    },
    "selectors": {
        "exact_spec_attention": 1,
        "batched_exact_moe": 1,
        "fused_w1_route_w2": 1,
        "route_interleave": 1,
        "shared_elementwise": 1,
        "qknorm_rope": 1,
        "w1_n_tile": 64,
    },
    "request": {
        "concurrency": 1,
        "max_tokens": 512,
        "seed": 1,
        "return_token_ids": True,
        "enable_thinking": False,
        "prefix_caching": False,
        "async_scheduling": False,
        "kv_cache_dtype": "bfloat16",
    },
}
Path(out).write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
PY

  setsid /usr/bin/env -i \
    PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    HOME="$leg_dir/private-home" TMP="$leg_dir/private-tmp" TEMP="$leg_dir/private-tmp" TMPDIR="$leg_dir/private-tmp" \
    HF_HOME="$leg_dir/private-cache/hf" HF_HUB_CACHE="$leg_dir/private-cache/hf/hub" TRANSFORMERS_CACHE="$leg_dir/private-cache/hf/transformers" \
    VLLM_CACHE_ROOT="$leg_dir/private-cache/vllm" TORCHINDUCTOR_CACHE_DIR="$leg_dir/private-cache/torchinductor" TRITON_CACHE_DIR="$leg_dir/private-cache/triton" SYCL_CACHE_DIR="$leg_dir/private-cache/sycl" NUMBA_CACHE_DIR="$leg_dir/private-cache/numba" PYTHONPYCACHEPREFIX="$leg_dir/private-cache/pycache" \
    XDG_CACHE_HOME="$leg_dir/private-cache" XDG_CONFIG_HOME="$leg_dir/private-xdg/config" XDG_DATA_HOME="$leg_dir/private-xdg/data" XDG_STATE_HOME="$leg_dir/private-xdg/state" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 PYTHONPATH="$vllm_root:$kernel_root" \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD= \
    ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 TORCH_XCCL_ASYNC_ERROR_HANDLING=1 \
    LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
    VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 \
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1 VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1 VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
    VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 \
    VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 \
    VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7 \
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1 VLLM_USE_BREAKABLE_CUDAGRAPH=1 XPU_GRAPH=1 VLLM_XPU_ENABLE_XPU_GRAPH=1 \
    "$serve_script" "$leg_dir" >"$leg_dir/server.log" 2>&1 &
  server_pid="$!"
  printf '%s\n' "$server_pid" > "$leg_dir/server.pid"

  for _ in $(seq 1 180); do
    if curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1; then
      ready=1
      break
    fi
    service_alive || {
      tail -160 "$leg_dir/server.log" >&2
      die "service exited before health for $leg"
    }
    sleep 5
  done
  (( ready == 1 )) || die "service startup timed out for $leg"
  tr '\0' '\n' < "/proc/$server_pid/environ" | LC_ALL=C sort \
    > "$leg_dir/service-environment.txt"

  curl -fsS http://127.0.0.1:18080/metrics > "$leg_dir/metrics-before.prom"
  "$venv_python" "$benchmark" \
    --base-url http://127.0.0.1:18080 \
    --model laguna-s-2.1-int4 \
    --suite experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json \
    --max-tokens 512 \
    --metric-tokens 100 \
    --seed 1 \
    --timeout 1800 \
    --return-token-ids \
    --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
    --out "$leg_dir/bench.json" \
    > "$leg_dir/bench.stdout"
  curl -fsS http://127.0.0.1:18080/metrics > "$leg_dir/metrics-after.prom"
  "$venv_python" "$comparator" \
    --teacher "$teacher" \
    --candidate "$leg_dir/bench.json" \
    --out "$leg_dir/exactness-vs-q1.json" \
    > "$leg_dir/exactness-vs-q1.stdout"

  stop_service || stop_status=1
  assert_no_workers "$leg_dir/post-workers.txt" || worker_status=1
  capture_idle "$leg_dir/post-idle.json" || idle_status=1
  printf 'stop_status=%s\nworker_status=%s\nidle_status=%s\n' \
    "$stop_status" "$worker_status" "$idle_status" > "$leg_dir/cleanup-status.txt"
  (( stop_status == 0 && worker_status == 0 && idle_status == 0 )) \
    || die "cleanup or device idle proof failed for $leg"
  mv -- "$rpc_dir" "$leg_dir/rpc-after-stop"
  active_leg_dir=""
}

cd "$repo_root"
run_leg start-a "$rpc_a"
run_leg start-b "$rpc_b"

"$venv_python" "$comparator" \
  --teacher "$run_dir/start-a/bench.json" \
  --candidate "$run_dir/start-b/bench.json" \
  --out "$run_dir/cross-start.json" \
  > "$run_dir/cross-start.stdout"
"$venv_python" "$analyzer" --run-dir "$run_dir" --out "$run_dir/analysis.json"
capture_idle "$run_dir/final-idle.json" || die "final device idle proof failed"
echo "Laguna M8 graph endpoint qualification PASS: $run_dir"
