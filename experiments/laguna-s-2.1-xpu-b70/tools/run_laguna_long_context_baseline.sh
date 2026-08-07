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
readonly expected_vllm_commit="${REPRO_EXPECTED_VLLM_COMMIT:-}"
readonly expected_kernel_commit="${REPRO_EXPECTED_KERNEL_COMMIT:-}"
readonly venv_python="$venv_root/bin/python"
readonly benchmark="$script_dir/bench_laguna_long_context.py"
readonly service="$script_dir/serve_laguna_long_context_nvme.sh"
readonly suite="${LAGUNA_LONG_SUITE:-$repo_root/experiments/laguna-s-2.1-xpu-b70/long-context-suite-v1.json}"
# The lock pins kernel binary SHA256s, so a deliberately rebuilt kernel tree
# needs its own lock. Default unchanged; diagnostics point at their own.
readonly runtime_lock="${LAGUNA_RUNTIME_LOCK:-$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-shared-elementwise-m12.json}"
readonly runtime_verifier="$repo_root/repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-runtime.py"
readonly xpumem_module=/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/vllm_xpu_kernels/xpumem_allocator.abi3.so
readonly kernel_package="$kernel_root/vllm_xpu_kernels"
readonly native_library_path="$kernel_package:$venv_root/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib"
readonly frozen_path="$venv_root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
readonly rpc_tag="$(printf '%s' "$run_dir" | sha256sum | cut -c1-12)"
readonly rpc_dir="$LAGUNA_NVME_TMP_ROOT/l${rpc_tag:0:6}"
readonly max_model_len="${LAGUNA_MAX_MODEL_LEN:-32768}"
readonly max_num_batched_tokens="${LAGUNA_MAX_NUM_BATCHED_TOKENS:-8192}"
readonly max_num_scheduled_tokens="${LAGUNA_MAX_NUM_SCHEDULED_TOKENS:-auto}"
readonly gpu_util="${LAGUNA_GPU_UTIL:-0.90}"
readonly request_timeout="${LAGUNA_LONG_TIMEOUT:-900}"
readonly selected_case_ids_csv="${LAGUNA_LONG_CASE_IDS:-}"
readonly min_mem_available_kb="${LAGUNA_MIN_MEM_AVAILABLE_KB:-12582912}"
readonly min_swap_free_kb="${LAGUNA_MIN_SWAP_FREE_KB:-4194304}"
readonly min_swap_total_kb="${LAGUNA_MIN_SWAP_TOTAL_KB:-0}"
readonly required_swap_layout="${LAGUNA_REQUIRED_SWAP_LAYOUT:-}"
readonly low_swap_min_mem_available_kb="${LAGUNA_LOW_SWAP_MIN_MEM_AVAILABLE_KB:-16777216}"
readonly oracle="${LAGUNA_LONG_ORACLE:-}"
readonly require_oracle="${LAGUNA_REQUIRE_ORACLE:-0}"
readonly exact_prefill_chunks="${LAGUNA_EXACT_PREFILL_CHUNKS:-0}"
readonly candidate_profile="${LAGUNA_LONG_CANDIDATE_PROFILE:-q12}"
readonly long_depth="${LAGUNA_LONG_DEPTH:-}"
# The eager fan-out arm must not capture graphs: graph replay executes no
# Python, so instrumentation in the model forward cannot observe decode steps.
readonly graph_flag="$([[ "${LAGUNA_EAGER_FANOUT:-0}" == 1 ]] && echo 0 || echo 1)"
readonly target_revision=4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb
readonly draft_revision=5e07c246915c86dc6920fead03d019989224f2ba
readonly model_manifest=/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/nvme-files.sha256
readonly model_manifest_sha256=45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac

case "$candidate_profile" in
  q12)
    readonly candidate_m=12 candidate_spec=11 candidate_draft_topology=14/13
    ;;
  q8|q8fp8)
    readonly candidate_m=8 candidate_spec=7 candidate_draft_topology=none
    ;;
  qdepth)
    # Depth-sweep arm. Only widths with a fused target QKNorm+RoPE path are
    # measurable; the launcher refuses the rest with the specific reason.
    # Depth 0 is the diagnostic width-1 no-drafter arm; it isolates what graph
    # capture alone is worth, which neither depth 11 nor depth 7 can show.
    [[ "$long_depth" == 11 || "$long_depth" == 7 || "$long_depth" == 0 ]] \
      || { echo "qdepth requires LAGUNA_LONG_DEPTH=11, 7, or 0" >&2; exit 2; }
    readonly candidate_m="$((long_depth + 1))" candidate_spec="$long_depth" \
      candidate_draft_topology=none
    ;;
  *)
    echo "LAGUNA_LONG_CANDIDATE_PROFILE must be q12, q8, q8fp8, or qdepth" >&2
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
  "$suite" "$runtime_lock" "$runtime_verifier" "$xpumem_module" "$model_manifest"; do
  [[ -e "$path" ]] || die "missing required path: $path"
done
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
readonly vllm_commit="$(git -C "$vllm_root" rev-parse HEAD)"
readonly kernel_commit="$(git -C "$kernel_root" rev-parse HEAD)"
[[ -z "$expected_vllm_commit" || "$vllm_commit" == "$expected_vllm_commit" ]] \
  || die "vLLM commit does not match REPRO_EXPECTED_VLLM_COMMIT"
[[ -z "$expected_kernel_commit" || "$kernel_commit" == "$expected_kernel_commit" ]] \
  || die "kernel commit does not match REPRO_EXPECTED_KERNEL_COMMIT"
[[ "$(sha256sum "$model_manifest" | cut -d' ' -f1)" == "$model_manifest_sha256" ]] \
  || die "Laguna model manifest hash mismatch"
[[ -z "$oracle" || -f "$oracle" ]] || die "missing oracle: $oracle"
[[ "$exact_prefill_chunks" == 0 || "$exact_prefill_chunks" == 1 ]] \
  || die "LAGUNA_EXACT_PREFILL_CHUNKS must be zero or one"
[[ "$role" == candidate || "$exact_prefill_chunks" == 0 ]] \
  || die "exact prefill chunks are only valid for the candidate"
[[ "$candidate_profile" == q12 || "$exact_prefill_chunks" == 0 ]] \
  || die "exact prefill chunks are only valid for the q12 candidate"
case "$max_num_batched_tokens" in
  4096|8192|8202|16384|32768) ;;
  8184|8188)
    [[ "$role" == candidate && "$candidate_profile" == qdepth ]] \
      || die "batched=$max_num_batched_tokens is reserved for the qdepth depth-sweep candidate"
    ;;
  8182)
    # Also the speculation-off teacher's partition-aligned budget; see the
    # launcher for why 8192 gives the teacher the rejected partition instead.
    [[ "$role" == teacher || ( "$role" == candidate && "$candidate_profile" == qdepth ) ]] \
      || die "batched=8182 is reserved for the qdepth candidate and the partition-aligned teacher"
    ;;
  *) die "LAGUNA_MAX_NUM_BATCHED_TOKENS must be 4096, 8182, 8184, 8188, 8192, 8202, 16384, or 32768" ;;
esac
if [[ "$candidate_profile" == qdepth && "$role" == candidate ]]; then
  # Keep the derived per-step budget, and therefore the 32,640-token prefill
  # partition, identical to the incumbent at every depth. With no speculative
  # config the scheduler reserves nothing and falls back to the batched value,
  # so the no-drafter arm pins 8182 directly rather than 8182+(depth-1).
  if [[ "${LAGUNA_NOSPEC_GRAPH:-0}" == 1 ]]; then
    (( max_num_batched_tokens == 8182 )) \
      || die "the no-drafter arm needs LAGUNA_MAX_NUM_BATCHED_TOKENS=8182"
  else
    (( max_num_batched_tokens - candidate_spec + 1 == 8182 )) \
      || die "qdepth depth $candidate_spec needs LAGUNA_MAX_NUM_BATCHED_TOKENS=$((8182 + candidate_spec - 1))"
  fi
fi
case "$max_num_scheduled_tokens" in
  auto) ;;
  8192)
    [[ "$role" == candidate && "$candidate_profile" == q12 \
      && "$exact_prefill_chunks" == 1 \
      && "$max_num_batched_tokens" == 8202 ]] \
      || die "scheduled-token alignment requires q12 exact-prefill candidate with batched=8202 and scheduled=8192"
    ;;
  *) die "LAGUNA_MAX_NUM_SCHEDULED_TOKENS must be auto or 8192" ;;
esac
[[ "$max_num_batched_tokens" != 8202 || "$max_num_scheduled_tokens" == 8192 ]] \
  || die "batched=8202 is reserved for the explicit scheduled=8192 alignment treatment"
if [[ "$max_num_scheduled_tokens" == auto ]]; then
  # Parallel drafting reserves depth-1 slots per sequence, so the candidate's
  # effective budget is the batched one less that reservation. A no-drafter arm
  # reserves nothing and keeps the batched budget, exactly as the teacher does.
  if [[ "$role" == candidate && "${LAGUNA_NOSPEC_GRAPH:-0}" != 1 ]]; then
    readonly expected_effective_scheduled_tokens="$((max_num_batched_tokens - candidate_spec + 1))"
  else
    readonly expected_effective_scheduled_tokens="$max_num_batched_tokens"
  fi
else
  readonly expected_effective_scheduled_tokens="$max_num_scheduled_tokens"
fi
awk -v value="$gpu_util" 'BEGIN { exit !(value > 0 && value < 1) }' \
  || die "LAGUNA_GPU_UTIL must be between zero and one"
[[ "$request_timeout" =~ ^[0-9]+$ && "$request_timeout" -ge 1 ]] \
  || die "LAGUNA_LONG_TIMEOUT must be a positive integer"
[[ "$min_mem_available_kb" =~ ^[0-9]+$ ]] \
  || die "LAGUNA_MIN_MEM_AVAILABLE_KB must be a non-negative integer"
[[ "$min_swap_free_kb" =~ ^[0-9]+$ ]] \
  || die "LAGUNA_MIN_SWAP_FREE_KB must be a non-negative integer"
[[ "$min_swap_total_kb" =~ ^[0-9]+$ ]] \
  || die "LAGUNA_MIN_SWAP_TOTAL_KB must be a non-negative integer"
[[ "$low_swap_min_mem_available_kb" =~ ^[0-9]+$ ]] \
  || die "LAGUNA_LOW_SWAP_MIN_MEM_AVAILABLE_KB must be a non-negative integer"
[[ "$require_oracle" == 0 || "$require_oracle" == 1 ]] \
  || die "LAGUNA_REQUIRE_ORACLE must be zero or one"
[[ "$require_oracle" == 0 || -n "$oracle" ]] \
  || die "LAGUNA_REQUIRE_ORACLE=1 requires LAGUNA_LONG_ORACLE"
readonly swap_total_kb="$(awk '$1 == "SwapTotal:" { print $2 }' /proc/meminfo)"
(( swap_total_kb >= min_swap_total_kb )) \
  || die "host SwapTotal ${swap_total_kb} kB is below required ${min_swap_total_kb} kB"
case "$required_swap_layout" in
  "") ;;
  laguna-longctx-24g)
    readonly observed_swap_layout="$(awk 'NR > 1 { print $1 ":" $3 }' /proc/swaps | sort)"
    readonly expected_swap_layout=$'/swap-laguna-longctx.img:16777212\n/swap.img:8388604'
    [[ "$observed_swap_layout" == "$expected_swap_layout" ]] \
      || die "active swap layout does not match the frozen Laguna 24 GiB layout"
    ;;
  *) die "unsupported LAGUNA_REQUIRED_SWAP_LAYOUT: $required_swap_layout" ;;
esac
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
    "$vllm_commit" "$kernel_commit"
  printf 'expected_vllm_commit=%s\nexpected_kernel_commit=%s\n' \
    "$expected_vllm_commit" "$expected_kernel_commit"
  printf 'target_revision=%s\ndraft_revision=%s\n' \
    "$target_revision" "$draft_revision"
  printf 'model_manifest=%s\nmodel_manifest_sha256=%s\n' \
    "$model_manifest" "$model_manifest_sha256"
  printf 'target_root=%s\ndraft_root=%s\n' \
    "$LAGUNA_NVME_TARGET_ROOT" "$LAGUNA_NVME_DRAFT_ROOT"
  printf 'target_config_sha256=%s\ndraft_config_sha256=%s\n' \
    "$(sha256sum "$LAGUNA_NVME_TARGET_ROOT/config.json" | cut -d' ' -f1)" \
    "$(sha256sum "$LAGUNA_NVME_DRAFT_ROOT/config.json" | cut -d' ' -f1)"
  printf 'max_model_len=%s\nmax_num_batched_tokens=%s\n' \
    "$max_model_len" "$max_num_batched_tokens"
  printf 'max_num_scheduled_tokens=%s\nexpected_effective_scheduled_tokens=%s\n' \
    "$max_num_scheduled_tokens" "$expected_effective_scheduled_tokens"
  printf 'enable_chunked_prefill=true\nmax_num_seqs=1\nblock_size=64\n'
  printf 'kv_cache_dtype=bfloat16\ngpu_memory_utilization=%s\n' "$gpu_util"
  printf 'prefix_caching=false\nasync_scheduling=%s\n' \
    "$([[ "$role" == candidate ]] && echo false || echo true)"
  printf 'request_timeout_seconds=%s\nselected_case_ids=%s\n' \
    "$request_timeout" "$selected_case_ids_csv"
  printf 'suite=%s\nexact_prefill_chunks=%s\n' \
    "$suite" "$exact_prefill_chunks"
  printf 'suite_sha256=%s\nruntime_lock_sha256=%s\n' \
    "$(sha256sum "$suite" | cut -d' ' -f1)" \
    "$(sha256sum "$runtime_lock" | cut -d' ' -f1)"
  printf 'candidate_profile=%s\ncandidate_m=%s\ncandidate_spec=%s\n' \
    "$candidate_profile" "$candidate_m" "$candidate_spec"
  printf 'memory_guard_min_available_kb=%s\nmemory_guard_min_swap_free_kb=%s\n' \
    "$min_mem_available_kb" "$min_swap_free_kb"
  printf 'memory_guard_min_swap_total_kb=%s\n' "$min_swap_total_kb"
  printf 'required_swap_layout=%s\n' "$required_swap_layout"
  printf 'memory_guard_low_swap_min_available_kb=%s\n' \
    "$low_swap_min_mem_available_kb"
  printf 'host_swap_total_kb=%s\nrequire_oracle=%s\n' \
    "$swap_total_kb" "$require_oracle"
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
readonly kernel_journal_start_epoch="$(date +%s)"
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
  local status="$?" stop_status=0 device_error_status=0
  trap - EXIT INT TERM
  set +e
  stop_memory_guard
  stop_benchmark
  stop_service || stop_status=1
  xpu-smi ps -j > "$run_dir/xpu-processes-after.json" 2>&1 || true
  journalctl -k -b --no-pager --since "@$kernel_journal_start_epoch" \
    > "$run_dir/kernel-journal.log" 2>&1 || stop_status=1
  grep -Ei \
    'guc.*(timeout|reset|error)|exec.*queue.*timeout|wedg|gpu.*(hang|reset|fault)|xe.*(timeout|reset|error|fail|fault|hang)|drm.*(timeout|reset|error|fail|fault|hang)' \
    "$run_dir/kernel-journal.log" > "$run_dir/device-error-scan.log" || true
  [[ ! -s "$run_dir/device-error-scan.log" ]] || device_error_status=1
  {
    date -u +timestamp_utc=%Y-%m-%dT%H:%M:%SZ
    free --bytes
    swapon --show --bytes
  } > "$run_dir/host-memory-after.txt"
  printf 'original_status=%s\nstop_status=%s\ndevice_error_status=%s\n' \
    "$status" "$stop_status" "$device_error_status" \
    > "$run_dir/cleanup-status.txt"
  if (( (stop_status != 0 || device_error_status != 0) && status == 0 )); then
    status=1
    printf 'FAIL_POSTRUN\n' > "$run_dir/run-status.txt"
  fi
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
  CCL_ATL_TRANSPORT="${CCL_ATL_TRANSPORT:-ofi}" CCL_TOPO_P2P_ACCESS=1
  FI_TCP_IFACE="$cluster_iface" CCL_KVS_IFACE="$cluster_iface"
  TORCH_XCCL_ASYNC_ERROR_HANDLING=1 LD_LIBRARY_PATH="$native_library_path"
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1
  # The batched-exact MoE kernel asserts local_experts=64/ep_size=4, so it is
  # also EP4-specific and must come off on BOTH arms of the EP-cost
  # diagnostic. Default unchanged.
  VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE="${LAGUNA_BATCHED_EXACT_MOE:-1}" VLLM_USE_AOT_COMPILE=0
  LAGUNA_MAX_MODEL_LEN="$max_model_len"
  LAGUNA_MAX_NUM_BATCHED_TOKENS="$max_num_batched_tokens"
  LAGUNA_MAX_NUM_SCHEDULED_TOKENS="$max_num_scheduled_tokens"
  LAGUNA_GPU_UTIL="$gpu_util"
  LAGUNA_LONG_CANDIDATE_PROFILE="$candidate_profile"
  LAGUNA_NOSPEC_GRAPH="${LAGUNA_NOSPEC_GRAPH:-0}"
  LAGUNA_NO_EP="${LAGUNA_NO_EP:-0}"
  VLLM_XPU_LAGUNA_ALLOW_NO_EP="${LAGUNA_NO_EP:-0}"
  VLLM_XPU_LAGUNA_ALLOW_NO_SPEC="${LAGUNA_ALLOW_NO_SPEC:-0}"
  LAGUNA_CUDAGRAPH_MODE="${LAGUNA_CUDAGRAPH_MODE:-PIECEWISE}"
  # Diagnostic, default 1 (off). Skips all but every Nth all-gather, which makes
  # the model's arithmetic wrong on purpose. It prices the count of four-rank
  # rendezvous while holding boundaries, topology and kernels fixed. Never a
  # record path; its throughput is not a rate Laguna can achieve.
  VLLM_XPU_LAGUNA_GATHER_SKIP_MOD="${LAGUNA_GATHER_SKIP_MOD:-1}"
  VLLM_XPU_LAGUNA_REPLICATED_ATTENTION="${LAGUNA_REPLICATED_ATTN:-0}"
  LAGUNA_KV_CACHE_BYTES="${LAGUNA_KV_CACHE_BYTES:-}"
  VLLM_XPU_LAGUNA_SKIP_EXPERTS="${LAGUNA_SKIP_EXPERTS:-0}"
  LAGUNA_UNITRACE="${LAGUNA_UNITRACE:-0}"
  VLLM_XPU_LAGUNA_COUNT_EXPERTS="${VLLM_XPU_LAGUNA_COUNT_EXPERTS:-0}"
  LAGUNA_EAGER_FANOUT="${LAGUNA_EAGER_FANOUT:-0}"
  VLLM_ENGINE_READY_TIMEOUT_S="${VLLM_ENGINE_READY_TIMEOUT_S:-1800}"
  PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF:-}"
  LAGUNA_DRAFT_ROOT_OVERRIDE="${LAGUNA_DRAFT_ROOT_OVERRIDE:-}"
  LAGUNA_EP_COST_DIAGNOSTIC="${LAGUNA_EP_COST_DIAGNOSTIC:-0}"
  LAGUNA_ASYNC_SCHED="${LAGUNA_ASYNC_SCHED:-0}"
  VLLM_XPU_LAGUNA_SYNC_COUNT="${VLLM_XPU_LAGUNA_SYNC_COUNT:-0}"
  LAGUNA_PROFILE_DIR="${LAGUNA_PROFILE_DIR:-}"
  LAGUNA_PROFILE_DELAY="${LAGUNA_PROFILE_DELAY:-6}"
  LAGUNA_PROFILE_ITERS="${LAGUNA_PROFILE_ITERS:-25}"
)
# An empty FI_PROVIDER is not the same as unset: libfabric then matches no
# provider and oneCCL fails ATL init. Only pass it when actually chosen.
[[ -z "${FI_PROVIDER:-}" ]] || common_env+=(FI_PROVIDER="$FI_PROVIDER")
# The fork tests these for `is None`, not emptiness, so exporting them empty
# under `env -i` would fail the replay-trace contract on every ordinary run.
# Pass them only when actually tracing.
if [[ "${LAGUNA_UNITRACE:-0}" == 1 ]]; then
  [[ -n "${LAGUNA_TRACE_SESSION:-}" && -n "${LAGUNA_UNITRACE_BIN:-}" && -n "${LAGUNA_UNITRACE_SHA256:-}" ]] \
    || die "LAGUNA_UNITRACE=1 needs LAGUNA_TRACE_SESSION, LAGUNA_UNITRACE_BIN and LAGUNA_UNITRACE_SHA256"
  common_env+=(
    LAGUNA_UNITRACE_BIN="$LAGUNA_UNITRACE_BIN"
    LAGUNA_UNITRACE_OUTPUT="${LAGUNA_UNITRACE_OUTPUT:-unitrace}"
    VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION="$LAGUNA_TRACE_SESSION"
    VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE="$LAGUNA_UNITRACE_BIN"
    VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE_SHA256="$LAGUNA_UNITRACE_SHA256"
  )
fi
# Per-segment replay profile. The reader parses the sample count, so an empty
# value is a hard error rather than "off": pass both or neither.
if [[ -n "${LAGUNA_REPLAY_PROFILE_ROOT:-}" ]]; then
  [[ -n "${LAGUNA_REPLAY_PROFILE_SAMPLES:-}" ]] \
    || die "LAGUNA_REPLAY_PROFILE_ROOT needs LAGUNA_REPLAY_PROFILE_SAMPLES"
  common_env+=(
    VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT="$LAGUNA_REPLAY_PROFILE_ROOT"
    VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES="$LAGUNA_REPLAY_PROFILE_SAMPLES"
  )
fi
if [[ "$role" == candidate ]]; then
  common_env+=(
    VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
    VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
    VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA="$graph_flag"
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
    VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS="${LAGUNA_INLINE_ATTN:-0}"
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
    VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT="${LAGUNA_EVENT_PROFILE_ROOT:-}"
    VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_TARGET_ONLY="${LAGUNA_EVENT_PROFILE_TARGET_ONLY:-0}"
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
    VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph_flag"
    VLLM_USE_BREAKABLE_CUDAGRAPH="$graph_flag" XPU_GRAPH="$graph_flag"
    VLLM_XPU_ENABLE_XPU_GRAPH="$graph_flag" VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0
    VLLM_XPU_LAGUNA_CAPTURE_FILTER_DEBUG=1
  )
  if [[ "$candidate_profile" == q12 ]]; then
    common_env+=(
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=1
      VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=1
      VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1
      VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1
      VLLM_XPU_LAGUNA_DFLASH_FP8_Q8=0
      VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=1
      VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=1
      # The shared-elementwise contract requires EP4, so measuring the cost of
      # expert parallelism means turning this selector off on BOTH arms. That
      # confounds absolute throughput, but the EP-on/EP-off delta stays clean.
      VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE="${LAGUNA_M12_SHARED:-1}"
      VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0
      VLLM_XPU_LAGUNA_DECODE_GRF128=1
      VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES="${LAGUNA_TRANSPOSED_SCALES:-1}"
    )
  elif [[ "$candidate_profile" == qdepth ]]; then
    # Every selector the vLLM fork pins to one depth or one verifier width is
    # off at every depth, so the only arm-to-arm difference is the draft depth.
    common_env+=(
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=0
      VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=0
      VLLM_XPU_LAGUNA_DFLASH_FP8_Q8=0
      VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=0
      VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=0
      VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=0
      VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0
      VLLM_XPU_LAGUNA_M12_MAPPED_GATHER_SCALE_ADD=0
      VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE=0
      VLLM_XPU_LAGUNA_DECODE_GRF128=0
      VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=0
    )
  elif [[ "$candidate_profile" == q8 ]]; then
    common_env+=(
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=0
      VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=0
      VLLM_XPU_LAGUNA_DFLASH_FP8_Q8=0
      VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH=0
      VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS=0
      VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE=0
      VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1
      VLLM_XPU_LAGUNA_DECODE_GRF128=0
      VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES=0
    )
  else
    common_env+=(
      VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=0
      VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1
      VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1
      VLLM_XPU_LAGUNA_DFLASH_FP8_Q8=1
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

# Profiling arm: arm the profiler before the request. delay_iterations skips
# the chunked-prefill iterations so the captured window is decode steps only.
if [[ -n "${LAGUNA_PROFILE_DIR:-}" ]]; then
  # /health can answer before the profiler endpoint is reachable when the server
  # is started with torch_profiler_dir, so a single POST races startup: it
  # returned curl(7) against a server that then stayed up for 13 minutes.
  profile_started=0
  for _ in $(seq 1 30); do
    if curl -fsS -X POST http://127.0.0.1:18080/start_profile >/dev/null 2>&1; then
      profile_started=1
      break
    fi
    service_alive || die "service exited while arming the profiler"
    sleep 2
  done
  (( profile_started == 1 )) || die "profiler failed to start"
fi

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
if [[ -n "${LAGUNA_PROFILE_DIR:-}" ]]; then
  curl -fsS -X POST http://127.0.0.1:18080/stop_profile >/dev/null || true
  sleep 20
fi
(( benchmark_status == 0 )) || exit "$benchmark_status"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-after.prom"

if [[ "$role" == candidate ]]; then
  topology_count() {
    local rank="$1" verb="$2" graphs="$3" eager_breaks="$4"
    grep -F "$verb audited breakable cudagraph for BatchDescriptor(num_tokens=${candidate_m}," \
      "$run_dir/server.log" \
      | grep -F "(Worker_TP${rank}_EP${rank} " \
      | grep -Fc "BreakableCUDAGraphCapture(graphs=$graphs, eager_breaks=$eager_breaks)" \
      || true
  }
  all_topology_count="$(grep -Fc 'BreakableCUDAGraphCapture(graphs=' "$run_dir/server.log" || true)"
  # Inlining attention records all 48 attention calls into their surrounding
  # segments, retiring each boundary and the graph it started: 146/145 -> 98/97.
  # The count stays pinned, so any drift other than the one the selector
  # explains still fails.
  # Replicated attention retires the 48 attention-O all-gathers instead of the
  # 48 attention boundaries, which is a different 48 but the same arithmetic.
  # `set -e` aborts on a false `[[ ]] && ...` list, so use explicit ifs.
  retired=0
  if [[ "${LAGUNA_INLINE_ATTN:-0}" == 1 ]]; then retired=$((retired + 48)); fi
  if [[ "${LAGUNA_REPLICATED_ATTN:-0}" == 1 ]]; then retired=$((retired + 48)); fi
  # Skipping the experts also retires the 47 MoE final-combine gathers.
  if [[ "${LAGUNA_SKIP_EXPERTS:-0}" == 1 ]]; then retired=$((retired + 47)); fi
  target_graphs=$((146 - retired)) target_eager_breaks=$((145 - retired))
  for rank in 0 1 2 3; do
    (( $(topology_count "$rank" Captured "$target_graphs" "$target_eager_breaks") == 1 )) \
      || die "candidate target capture topology is not exactly once on rank $rank"
    (( $(topology_count "$rank" Replayed "$target_graphs" "$target_eager_breaks") == 1 )) \
      || die "candidate target replay topology is not exactly once on rank $rank"
    if [[ "$candidate_profile" == q12 ]]; then
      (( $(topology_count "$rank" Captured 14 13) == 1 )) \
        || die "q12 draft capture topology is not exactly once on rank $rank"
      (( $(topology_count "$rank" Replayed 14 13) == 1 )) \
        || die "q12 draft replay topology is not exactly once on rank $rank"
    else
      (( $(topology_count "$rank" Captured 14 13) == 0 )) \
        || die "$candidate_profile unexpectedly captured a draft graph on rank $rank"
      (( $(topology_count "$rank" Replayed 14 13) == 0 )) \
        || die "$candidate_profile unexpectedly replayed a draft graph on rank $rank"
    fi
  done
  [[ "$candidate_profile" != q12 && "$all_topology_count" == 8 \
    || "$candidate_profile" == q12 && "$all_topology_count" == 16 ]] \
    || die "candidate emitted an unexpected Breakable topology line"
  if [[ "$max_num_scheduled_tokens" == auto && "${LAGUNA_NOSPEC_GRAPH:-0}" == 1 ]]; then
    # vLLM only emits "set to N based on" when speculation reserves slots, so a
    # no-drafter arm has no reduction to report and the line never appears. The
    # launcher's own derivation is the stronger proof: it refuses to start
    # unless the derived budget equals the batched one.
    grep -Fq "Laguna qdepth arm: depth=$candidate_spec width=$candidate_m batched=$max_num_batched_tokens derived_scheduled=$expected_effective_scheduled_tokens" \
      "$run_dir/server.log" \
      || die "no-drafter scheduler budget was not proved in server.log"
  elif [[ "$max_num_scheduled_tokens" == auto ]]; then
    grep -Fq "max_num_scheduled_tokens is set to $expected_effective_scheduled_tokens based on" \
      "$run_dir/server.log" \
      || die "automatic runtime scheduler budget was not proved in server.log"
  else
    grep -Fq "Laguna long scheduler budget: batched=$max_num_batched_tokens scheduled=$max_num_scheduled_tokens" \
      "$run_dir/server.log" \
      || die "explicit launcher scheduler budget was not proved in server.log"
    explicit_budget_log="$(grep -F 'non-default args:' "$run_dir/server.log" \
      | grep -F "'max_num_batched_tokens': $max_num_batched_tokens" \
      | grep -F "'max_num_scheduled_tokens': $max_num_scheduled_tokens" \
      || true)"
    [[ -n "$explicit_budget_log" ]] \
      || die "explicit vLLM runtime scheduler budget was not proved in server.log"
  fi
fi

stop_service
server_pid=""
stop_memory_guard
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 \
  || die "vLLM workers survived ordinary shutdown"
printf 'PASS\n' > "$run_dir/run-status.txt"
