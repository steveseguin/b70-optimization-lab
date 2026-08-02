#!/usr/bin/env bash
# Cold diagnostic 32K service run; never emits a LocalMaxxing score.
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

role="${1:?usage: run_laguna_long_context_baseline.sh candidate|teacher RUN_DIR}"
run_dir="${2:?usage: run_laguna_long_context_baseline.sh candidate|teacher RUN_DIR}"
case "$role" in candidate|teacher) ;; *) echo "unsupported role: $role" >&2; exit 2 ;; esac

readonly venv_root="${REPRO_VENV_ROOT:-/home/steve/.venvs/deepseek-v4-xpu}"
readonly vllm_root="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731}"
readonly kernel_root="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731}"
readonly venv_python="$venv_root/bin/python"
readonly benchmark="$script_dir/bench_laguna_long_context.py"
readonly service="$script_dir/serve_laguna_long_context_nvme.sh"
readonly suite="${LAGUNA_LONG_SUITE:-$repo_root/experiments/laguna-s-2.1-xpu-b70/long-context-suite-v1.json}"
readonly runtime_lock="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-shared-elementwise-m12.json"
readonly runtime_verifier="$repo_root/repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-runtime.py"
readonly xpumem_module=/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/vllm_xpu_kernels/xpumem_allocator.abi3.so
readonly kernel_package="$kernel_root/vllm_xpu_kernels"
readonly native_library_path="$kernel_package:$venv_root/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib"
readonly frozen_path="$venv_root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
readonly rpc_tag="$(printf '%s' "$run_dir" | sha256sum | cut -c1-12)"
readonly rpc_dir="$LAGUNA_NVME_TMP_ROOT/l${rpc_tag:0:6}"
readonly max_model_len="${LAGUNA_MAX_MODEL_LEN:-32768}"
readonly max_num_batched_tokens="${LAGUNA_MAX_NUM_BATCHED_TOKENS:-8192}"
readonly gpu_util="${LAGUNA_GPU_UTIL:-0.90}"
readonly request_timeout="${LAGUNA_LONG_TIMEOUT:-900}"
readonly selected_case_ids_csv="${LAGUNA_LONG_CASE_IDS:-}"
readonly min_mem_available_kb="${LAGUNA_MIN_MEM_AVAILABLE_KB:-12582912}"
readonly min_swap_free_kb="${LAGUNA_MIN_SWAP_FREE_KB:-4194304}"
readonly low_swap_min_mem_available_kb="${LAGUNA_LOW_SWAP_MIN_MEM_AVAILABLE_KB:-16777216}"
readonly oracle="${LAGUNA_LONG_ORACLE:-}"
readonly exact_prefill_chunks="${LAGUNA_EXACT_PREFILL_CHUNKS:-0}"
readonly candidate_profile="${LAGUNA_LONG_CANDIDATE_PROFILE:-q12}"

case "$candidate_profile" in
  q12)
    readonly candidate_m=12 candidate_spec=11 candidate_draft_topology=14/13
    ;;
  q8)
    readonly candidate_m=8 candidate_spec=7 candidate_draft_topology=none
    ;;
  *)
    echo "LAGUNA_LONG_CANDIDATE_PROFILE must be q12 or q8" >&2
    exit 2
    ;;
esac

die() { echo "Laguna long-context baseline: $*" >&2; exit 2; }

laguna_cluster_iface() {
  local ip="${REPRO_CLUSTER_IP:-${LAGUNA_CLUSTER_IP:-10.0.0.65}}" iface
  iface="$(ip -o -4 addr show 2>/dev/null | awk -v ip="$ip" '$4 ~ "^"ip"/" {print $2; exit}')"
  [[ -n "$iface" ]] || return 1
  [[ "$(cat "/sys/class/net/$iface/operstate" 2>/dev/null)" == up ]] || return 1
  printf '%s\n' "$iface"
}

case "$run_dir" in "$LAGUNA_NVME_RUN_ROOT"/*) ;; *) die "run directory is outside the fixed NVMe run root" ;; esac
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run directory must be canonical"
for path in "$vllm_root" "$kernel_root" "$venv_python" "$benchmark" "$service" \
  "$suite" "$runtime_lock" "$runtime_verifier" "$xpumem_module"; do
  [[ -e "$path" ]] || die "missing required path: $path"
done
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
[[ -z "$oracle" || -f "$oracle" ]] || die "missing oracle: $oracle"
[[ "$exact_prefill_chunks" == 0 || "$exact_prefill_chunks" == 1 ]] \
  || die "LAGUNA_EXACT_PREFILL_CHUNKS must be zero or one"
[[ "$role" == candidate || "$exact_prefill_chunks" == 0 ]] \
  || die "exact prefill chunks are only valid for the candidate"
[[ "$candidate_profile" == q12 || "$exact_prefill_chunks" == 0 ]] \
  || die "exact prefill chunks are not valid for the q8 candidate"
awk -v value="$gpu_util" 'BEGIN { exit !(value > 0 && value < 1) }' \
  || die "LAGUNA_GPU_UTIL must be between zero and one"
[[ "$request_timeout" =~ ^[0-9]+$ && "$request_timeout" -ge 1 ]] \
  || die "LAGUNA_LONG_TIMEOUT must be a positive integer"
[[ "$min_mem_available_kb" =~ ^[0-9]+$ ]] \
  || die "LAGUNA_MIN_MEM_AVAILABLE_KB must be a non-negative integer"
[[ "$min_swap_free_kb" =~ ^[0-9]+$ ]] \
  || die "LAGUNA_MIN_SWAP_FREE_KB must be a non-negative integer"
[[ "$low_swap_min_mem_available_kb" =~ ^[0-9]+$ ]] \
  || die "LAGUNA_LOW_SWAP_MIN_MEM_AVAILABLE_KB must be a non-negative integer"
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || die "existing vLLM workers block run"
! ss -H -ltn 'sport = :18080' | grep -q . || die "port 18080 already has a listener"
[[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "RPC directory already exists"
rpc_probe="$rpc_dir/00000000-0000-0000-0000-000000000000"
(( ${#rpc_probe} <= 107 )) || die "RPC socket path exceeds the platform limit"
cluster_iface="$(laguna_cluster_iface)" || die "cannot resolve cluster interface"
readonly cluster_iface

laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
laguna_nvme_prepare_run_dir "$run_dir"
mkdir -p "$run_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
mkdir --mode=700 "$rpc_dir"
chmod -R 700 "$run_dir"

/usr/bin/env -i \
  PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  PYTHONPATH="$vllm_root:$kernel_root" LD_LIBRARY_PATH="$native_library_path" \
  "$venv_python" "$runtime_verifier" \
  --lock "$runtime_lock" --vllm-tree "$vllm_root" \
  --kernel-tree "$kernel_root" --venv-root "$venv_root" \
  --xpumem-module "$xpumem_module" \
  --json-out "$run_dir/runtime-verification.json" \
  > "$run_dir/runtime-verification.stdout"

{
  printf 'schema=laguna-long-context-baseline-v1\nrole=%s\n' "$role"
  printf 'vllm_commit=%s\nkernel_commit=%s\n' \
    "$(git -C "$vllm_root" rev-parse HEAD)" \
    "$(git -C "$kernel_root" rev-parse HEAD)"
  printf 'max_model_len=%s\nmax_num_batched_tokens=%s\n' \
    "$max_model_len" "$max_num_batched_tokens"
  printf 'enable_chunked_prefill=true\nmax_num_seqs=1\nblock_size=64\n'
  printf 'kv_cache_dtype=bfloat16\ngpu_memory_utilization=%s\n' "$gpu_util"
  printf 'prefix_caching=false\nasync_scheduling=%s\n' \
    "$([[ "$role" == candidate ]] && echo false || echo true)"
  printf 'request_timeout_seconds=%s\nselected_case_ids=%s\n' \
    "$request_timeout" "$selected_case_ids_csv"
  printf 'suite=%s\nexact_prefill_chunks=%s\n' \
    "$suite" "$exact_prefill_chunks"
  printf 'candidate_profile=%s\ncandidate_m=%s\ncandidate_spec=%s\n' \
    "$candidate_profile" "$candidate_m" "$candidate_spec"
  printf 'memory_guard_min_available_kb=%s\nmemory_guard_min_swap_free_kb=%s\n' \
    "$min_mem_available_kb" "$min_swap_free_kb"
  printf 'memory_guard_low_swap_min_available_kb=%s\n' \
    "$low_swap_min_mem_available_kb"
  printf 'host_swap_total_kb=%s\n' \
    "$(awk '$1 == "SwapTotal:" { print $2 }' /proc/meminfo)"
  printf 'q12_short_record_reference_conventional_tok_s=125.4619731637751\n'
  printf 'candidate_target_topology=146/145\ncandidate_draft_topology=%s\n' \
    "$candidate_draft_topology"
  printf 'oracle=%s\ncluster_iface=%s\nscored_measurement=false\n' "$oracle" "$cluster_iface"
  sha256sum "$benchmark" "$service" "$suite" "$runtime_lock" \
    "$venv_python" "$kernel_package/_C.abi3.so" \
    "$kernel_package/_xpu_C.abi3.so" "$kernel_package/_moe_C.abi3.so" \
    "$kernel_package/libgrouped_gemm_xe_2.so" \
    "$LAGUNA_NVME_TARGET_ROOT/config.json" \
    "$LAGUNA_NVME_DRAFT_ROOT/config.json"
} > "$run_dir/identity.txt"
xpu-smi ps -j > "$run_dir/xpu-processes-before.json" 2>&1 || true
{
  date -u +timestamp_utc=%Y-%m-%dT%H:%M:%SZ
  free --bytes
  swapon --show --bytes
} > "$run_dir/host-memory-before.txt"

server_pid=""
memory_guard_pid=""
benchmark_pid=""
service_alive() {
  [[ -n "$server_pid" ]] && (
    kill -0 "$server_pid" 2>/dev/null || kill -0 -- "-$server_pid" 2>/dev/null
  )
}
stop_memory_guard() {
  [[ -n "$memory_guard_pid" ]] || return 0
  kill "$memory_guard_pid" 2>/dev/null || true
  wait "$memory_guard_pid" 2>/dev/null || true
  memory_guard_pid=""
}
benchmark_alive() {
  [[ -n "$benchmark_pid" ]] && kill -0 "$benchmark_pid" 2>/dev/null
}
stop_benchmark() {
  local signal attempts
  [[ -n "$benchmark_pid" ]] || return 0
  for signal in TERM KILL; do
    benchmark_alive || break
    kill "-$signal" "$benchmark_pid" 2>/dev/null || true
    case "$signal" in TERM) attempts=10 ;; KILL) attempts=5 ;; esac
    for _ in $(seq 1 "$attempts"); do benchmark_alive || break; sleep 1; done
  done
  wait "$benchmark_pid" 2>/dev/null || true
  benchmark_pid=""
}
stop_service() {
  local signal attempts
  [[ -n "$server_pid" ]] || return 0
  for signal in INT TERM KILL; do
    service_alive || break
    kill "-$signal" -- "-$server_pid" 2>/dev/null || true
    kill "-$signal" "$server_pid" 2>/dev/null || true
    case "$signal" in INT) attempts=30 ;; TERM) attempts=15 ;; KILL) attempts=10 ;; esac
    for _ in $(seq 1 "$attempts"); do service_alive || break; sleep 1; done
  done
  wait "$server_pid" 2>/dev/null || true
  ! service_alive
}
finalize() {
  local status="$?" stop_status=0
  trap - EXIT INT TERM
  set +e
  stop_memory_guard
  stop_benchmark
  stop_service || stop_status=1
  xpu-smi ps -j > "$run_dir/xpu-processes-after.json" 2>&1 || true
  {
    date -u +timestamp_utc=%Y-%m-%dT%H:%M:%SZ
    free --bytes
    swapon --show --bytes
  } > "$run_dir/host-memory-after.txt"
  printf 'original_status=%s\nstop_status=%s\n' "$status" "$stop_status" \
    > "$run_dir/cleanup-status.txt"
  if [[ -e "$rpc_dir" && ! -e "$run_dir/rpc-after-stop" ]]; then
    mv -- "$rpc_dir" "$run_dir/rpc-after-stop" 2>/dev/null || true
  fi
  chmod -R a-w "$run_dir" 2>/dev/null || true
  exit "$status"
}
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

common_env=(
  PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8
  HOME="$run_dir/private-home" TMPDIR="$run_dir/private-tmp"
  HF_HOME="$run_dir/private-cache/hf"
  HF_HUB_CACHE="$run_dir/private-cache/hf/hub"
  TRANSFORMERS_CACHE="$run_dir/private-cache/hf/transformers"
  VLLM_CACHE_ROOT="$run_dir/private-cache/vllm"
  TORCHINDUCTOR_CACHE_DIR="$run_dir/private-cache/torchinductor"
  TRITON_CACHE_DIR="$run_dir/private-cache/triton"
  SYCL_CACHE_DIR="$run_dir/private-cache/sycl"
  NUMBA_CACHE_DIR="$run_dir/private-cache/numba"
  PYTHONPYCACHEPREFIX="$run_dir/private-cache/pycache"
  XDG_CACHE_HOME="$run_dir/private-cache"
  XDG_CONFIG_HOME="$run_dir/private-xdg/config"
  XDG_DATA_HOME="$run_dir/private-xdg/data"
  XDG_STATE_HOME="$run_dir/private-xdg/state"
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
  PYTHONHASHSEED=0 PYTHONPATH="$vllm_root:$kernel_root"
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1
  VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
  ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3
  CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1
  FI_TCP_IFACE="$cluster_iface" CCL_KVS_IFACE="$cluster_iface"
  TORCH_XCCL_ASYNC_ERROR_HANDLING=1 LD_LIBRARY_PATH="$native_library_path"
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1
  VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 VLLM_USE_AOT_COMPILE=0
  LAGUNA_MAX_MODEL_LEN="$max_model_len"
  LAGUNA_MAX_NUM_BATCHED_TOKENS="$max_num_batched_tokens"
  LAGUNA_GPU_UTIL="$gpu_util"
  LAGUNA_LONG_CANDIDATE_PROFILE="$candidate_profile"
)
if [[ "$role" == candidate ]]; then
  common_env+=(
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
    VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
    VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1
    VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
    VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0
    VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0
    VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0
    VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0
    VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0
    VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0
    VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0
    VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0
    VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=0
    VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS=0
    VLLM_XPU_LAGUNA_M8_INLINE_GATHERS=0
    VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0
    VLLM_XPU_LAGUNA_M8_W1_N_TILE=64
    VLLM_XPU_LAGUNA_M12_ATTENTION_GATE=0
    VLLM_XPU_LAGUNA_REPLICATED_EMBEDDING=0
    VLLM_XPU_LAGUNA_SCALE_VEC=1
    VLLM_XPU_LAGUNA_SCALE_FOLD=0
    VLLM_XPU_LAGUNA_SCALE_HOIST=0
    VLLM_XPU_LAGUNA_DEQUANT_MAD=0
    VLLM_XPU_LAGUNA_PREFETCH_DIST=6
    VLLM_XPU_LAGUNA_EXACT_MAX_M="$candidate_m"
    VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS="$exact_prefill_chunks"
    VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH=0
    VLLM_XPU_LAGUNA_DRAFT_IDENTITY_PROBE=0
    VLLM_XPU_LAGUNA_DFLASH_CAPTURE_ATTENTION_GRAPHS=0
    VLLM_XPU_LAGUNA_DFLASH_CAPTURE_COLLECTIVE_COPIES=0
    VLLM_XPU_LAGUNA_DFLASH_INPLACE_COLLECTIVES=0
    VLLM_XPU_LAGUNA_PARITY_PROBE=0
    VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT=
    VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_TARGET_ONLY=0
    VLLM_XPU_MXFP4_SMALL_M_N=
    VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0
    VLLM_XPU_V4_M1_BIASED_TOPK=0
    VLLM_XPU_V4_M1_ROUTER_NORM=0
    VLLM_DISABLE_SHARED_EXPERTS_STREAM=0
    VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256
    VLLM_TRACE_FUNCTION=0
    LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS="$candidate_spec"
    LAGUNA_LOCAL_ARGMAX=false LAGUNA_LOG_MOE_ROWS=0
    LAGUNA_M="$candidate_m" LAGUNA_SPEC="$candidate_spec"
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1
    VLLM_USE_BREAKABLE_CUDAGRAPH=1 XPU_GRAPH=1
    VLLM_XPU_ENABLE_XPU_GRAPH=1 VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0
    VLLM_XPU_LAGUNA_CAPTURE_FILTER_DEBUG=1
  )
  if [[ "$candidate_profile" == q12 ]]; then
    common_env+=(
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=1
      VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=1
      VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1
      VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1
      VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=1
      VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=1
      VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=1
      VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0
      VLLM_XPU_LAGUNA_DECODE_GRF128=1
      VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=1
    )
  else
    common_env+=(
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=0
      VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=0
      VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=0
      VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=0
      VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=0
      VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1
      VLLM_XPU_LAGUNA_DECODE_GRF128=0
      VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=0
    )
  fi
else
  common_env+=(
    XPU_GRAPH=0 VLLM_XPU_ENABLE_XPU_GRAPH=0
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=0
    VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=0
    VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0
    VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0
  )
fi

setsid /usr/bin/env -i "${common_env[@]}" \
  "$service" "$role" "$run_dir" > "$run_dir/server.log" 2>&1 &
server_pid="$!"
printf '%s\n' "$server_pid" > "$run_dir/server.pid"
printf 'timestamp_utc\tmem_available_kb\tswap_free_kb\taction\n' \
  > "$run_dir/memory-guard.tsv"
(
  while service_alive; do
    available_kb="$(awk '$1 == "MemAvailable:" { print $2 }' /proc/meminfo)"
    swap_free_kb="$(awk '$1 == "SwapFree:" { print $2 }' /proc/meminfo)"
    action=continue
    if (( available_kb < min_mem_available_kb \
          || (swap_free_kb < min_swap_free_kb \
              && available_kb < low_swap_min_mem_available_kb) )); then
      action=stop-service
    fi
    printf '%s\t%s\t%s\t%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$available_kb" "$swap_free_kb" "$action" \
      >> "$run_dir/memory-guard.tsv"
    if [[ "$action" == stop-service ]]; then
      printf 'memory guard stopped the service: MemAvailable=%s kB, SwapFree=%s kB\n' \
        "$available_kb" "$swap_free_kb" > "$run_dir/memory-guard-stop.txt"
      if [[ -s "$run_dir/benchmark.pid" ]]; then
        read -r active_benchmark_pid < "$run_dir/benchmark.pid" || true
        if [[ "$active_benchmark_pid" =~ ^[0-9]+$ ]]; then
          kill -TERM "$active_benchmark_pid" 2>/dev/null || true
        fi
      fi
      kill -TERM -- "-$server_pid" 2>/dev/null || true
      kill -TERM "$server_pid" 2>/dev/null || true
      break
    fi
    sleep 1
  done
) &
memory_guard_pid="$!"
for _ in $(seq 1 240); do
  curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1 && break
  service_alive || die "service exited before health"
  sleep 5
done
curl -fsS http://127.0.0.1:18080/health >/dev/null || die "service startup timed out"
tr '\0' '\n' < "/proc/$server_pid/environ" | LC_ALL=C sort \
  > "$run_dir/service-environment.txt"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-before.prom"

benchmark_args=(
  --base-url http://127.0.0.1:18080
  --model laguna-s-2.1-int4
  --model-path "$LAGUNA_NVME_TARGET_ROOT"
  --suite "$suite"
  --run-role "$role"
  --timeout "$request_timeout"
  --out "$run_dir/bench.json"
)
[[ -z "$oracle" ]] || benchmark_args+=(--oracle "$oracle")
if [[ -n "$selected_case_ids_csv" ]]; then
  IFS=',' read -r -a selected_case_ids <<< "$selected_case_ids_csv"
  for case_id in "${selected_case_ids[@]}"; do
    [[ "$case_id" =~ ^[A-Za-z0-9._-]+$ ]] \
      || die "invalid case ID in LAGUNA_LONG_CASE_IDS: $case_id"
    benchmark_args+=(--case-id "$case_id")
  done
fi
"$venv_python" "$benchmark" "${benchmark_args[@]}" \
  > "$run_dir/bench.stdout" &
benchmark_pid="$!"
printf '%s\n' "$benchmark_pid" > "$run_dir/benchmark.pid"
set +e
wait "$benchmark_pid"
benchmark_status="$?"
set -e
benchmark_pid=""
printf 'completed\n' > "$run_dir/benchmark.pid"
(( benchmark_status == 0 )) || exit "$benchmark_status"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-after.prom"

if [[ "$role" == candidate ]]; then
  topology_count() {
    local verb="$1" graphs="$2" eager_breaks="$3"
    grep -F "$verb audited breakable cudagraph for BatchDescriptor(num_tokens=${candidate_m}," \
      "$run_dir/server.log" \
      | grep -Fc "BreakableCUDAGraphCapture(graphs=$graphs, eager_breaks=$eager_breaks)" \
      || true
  }
  target_capture_count="$(topology_count Captured 146 145)"
  target_replay_count="$(topology_count Replayed 146 145)"
  draft_capture_count="$(topology_count Captured 14 13)"
  draft_replay_count="$(topology_count Replayed 14 13)"
  all_topology_count="$(grep -Fc 'BreakableCUDAGraphCapture(graphs=' "$run_dir/server.log" || true)"
  (( target_capture_count == 4 )) \
    || die "candidate target capture topology count is not exactly four"
  (( target_replay_count == 4 )) \
    || die "candidate target replay topology count is not exactly four"
  if [[ "$candidate_profile" == q12 ]]; then
    (( draft_capture_count == 4 )) \
      || die "q12 candidate draft capture topology count is not exactly four"
    (( draft_replay_count == 4 )) \
      || die "q12 candidate draft replay topology count is not exactly four"
    (( all_topology_count == 16 )) \
      || die "q12 candidate emitted an unexpected Breakable topology line"
  else
    (( draft_capture_count == 0 && draft_replay_count == 0 )) \
      || die "q8 candidate unexpectedly captured or replayed a draft graph"
    (( all_topology_count == 8 )) \
      || die "q8 candidate emitted an unexpected Breakable topology line"
  fi
fi

stop_service
server_pid=""
stop_memory_guard
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 \
  || die "vLLM workers survived ordinary shutdown"
printf 'PASS\n' > "$run_dir/run-status.txt"
