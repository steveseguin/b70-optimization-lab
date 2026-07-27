#!/usr/bin/env bash
# Reproducible target-only FP8 teacher or width-12/depth-11 FP8 candidate leg.
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
# shellcheck source=/dev/null
source "$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/laguna_nvme_paths.sh"

mode="${1:?usage: run_laguna_fp8_kv_leg.sh teacher|candidate LABEL RUN_DIR [TEACHER_JSON]}"
label="${2:?usage: run_laguna_fp8_kv_leg.sh teacher|candidate LABEL RUN_DIR [TEACHER_JSON]}"
run_dir="${3:?usage: run_laguna_fp8_kv_leg.sh teacher|candidate LABEL RUN_DIR [TEACHER_JSON]}"
teacher="${4:-}"
case "$mode" in teacher) [[ -z "$teacher" ]] ;; candidate) [[ -n "$teacher" ]] ;; *)
  echo "unsupported mode: $mode" >&2
  exit 2
esac

die() { echo "Laguna FP8 KV leg: $*" >&2; exit 2; }
check_hash() {
  [[ "$(sha256sum -- "$1" | awk '{print $1}')" == "$2" ]] \
    || die "SHA256 drift: $1"
}
cluster_iface() {
  local ip="${REPRO_CLUSTER_IP:-10.0.0.65}" iface
  iface="$(ip -o -4 addr show | awk -v ip="$ip" '$4 ~ "^"ip"/" {print $2; exit}')"
  [[ -n "$iface" ]] || return 1
  [[ "$(cat "/sys/class/net/$iface/operstate")" == up ]] || return 1
  printf '%s\n' "$iface"
}

readonly venv_root="${REPRO_VENV_ROOT:-/home/steve/.venvs/deepseek-v4-xpu}"
readonly vllm_root="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-fp8-kv-20260727}"
readonly kernel_root="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726}"
readonly venv_python="$venv_root/bin/python"
readonly frozen_path="$venv_root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
readonly native_library_path="$kernel_root/vllm_xpu_kernels:$venv_root/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib"
readonly server="$script_dir/serve_laguna_fp8_kv_nvme.sh"
readonly scale_audit="$script_dir/audit_checkpoint_fp8_kv_scales.py"
readonly suite="$repo_root/experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
readonly benchmark="$repo_root/scripts/bench-openai-realistic-suite.py"
readonly qualifier="$repo_root/scripts/qualify_realistic_window_metrics.py"
readonly comparator="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
readonly idle_wrapper="$repo_root/experiments/laguna-s-2.1-xpu-b70/tools/capture_laguna_m8_idle_snapshot.py"
readonly runtime_lock="$repo_root/repro/laguna-s-2.1-int4-b70-102tps-20260726/manifests/runtime-lock.json"
readonly runtime_verifier="$repo_root/repro/laguna-s-2.1-int4-b70-102tps-20260726/verify-runtime.py"
readonly xpumem_module=/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/vllm_xpu_kernels/xpumem_allocator.abi3.so
readonly fp8_run_root="$LAGUNA_NVME_RUN_ROOT/fp8-kv"
readonly expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
readonly expected_target_config=9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
readonly expected_draft_config=6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
readonly expected_scale_digest=3e6df440976ab2ed5229e1a39179cbc99d573c615386f223eeabc9de5ea9ddc0
readonly rpc_dir="$LAGUNA_NVME_TMP_ROOT/fp8kv-${label,,}"
readonly max_tokens="${LAGUNA_FP8_MAX_TOKENS:-512}"
[[ "$max_tokens" =~ ^[0-9]+$ ]] && (( max_tokens >= 100 && max_tokens <= 512 )) \
  || die "LAGUNA_FP8_MAX_TOKENS must be an integer from 100 through 512"
if [[ "$mode" == candidate ]]; then
  readonly graph=1 width12=1 execution_width=12 speculative_depth=11
  readonly expected_graph_topology=146/145
else
  readonly graph=0 width12=0 execution_width=1 speculative_depth=0
  readonly expected_graph_topology=none
fi

laguna_nvme_prepare_paths
mkdir -p -- "$fp8_run_root"
laguna_nvme_assert_fixed_path "$fp8_run_root"
case "$run_dir" in "$fp8_run_root"/*) ;; *) die "run is outside $fp8_run_root" ;; esac
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run path is not canonical"
[[ ! -e "$run_dir" ]] || die "run path already exists"
[[ ! -e "$rpc_dir" ]] || die "RPC path already exists"
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
for path in \
  "$venv_python" "$server" "$scale_audit" "$suite" "$benchmark" "$qualifier" \
  "$comparator" "$idle_wrapper" "$runtime_lock" "$runtime_verifier" \
  "$xpumem_module"; do
  [[ -e "$path" && "$(realpath -e -- "$path")" != /media/* ]] \
    || die "missing or USB-resident dependency: $path"
done
[[ "$mode" == teacher || -f "$teacher" ]] || die "missing FP8 teacher: $teacher"
check_hash "$suite" "$expected_suite"
check_hash "$LAGUNA_NVME_TARGET_ROOT/config.json" "$expected_target_config"
check_hash "$LAGUNA_NVME_DRAFT_ROOT/config.json" "$expected_draft_config"
iface="$(cluster_iface)" || die "cannot resolve the 10.0.0.65 cluster interface"
readonly iface
! ss -H -ltn 'sport = :18080' | grep -q . || die "port 18080 is occupied"
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null \
  || die "existing vLLM workers block the leg"

mkdir -p -- "$run_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state}}
mkdir --mode=700 "$rpc_dir"
chmod -R 700 -- "$run_dir"
"$venv_python" "$scale_audit" \
  --model "$LAGUNA_NVME_TARGET_ROOT" \
  --out "$run_dir/checkpoint-fp8-kv-scales.json" \
  > "$run_dir/checkpoint-fp8-kv-scales.stdout"
jq -e --arg digest "$expected_scale_digest" \
  '.digest == $digest and .layers == 48 and .scale_tensors == 96
   and .all_finite_positive == true and .unit_scale_count == 0' \
  "$run_dir/checkpoint-fp8-kv-scales.json" >/dev/null

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
  printf 'schema=laguna-fp8-kv-leg-v1\nmode=%s\nlabel=%s\n' "$mode" "$label"
  printf 'target_kv_cache_dtype=fp8\ntarget_kv_scale_mode=checkpoint-calibrated\n'
  printf 'target_kv_scale_digest=%s\ndraft_kv_cache_dtype=fp8\ndraft_kv_scale_mode=unit-uncalibrated\n' "$expected_scale_digest"
  printf 'calculate_kv_scales=false\npersistent_bf16_kv_views=false\n'
  printf 'vllm_commit=%s\nkernel_commit=%s\nmain_repo_commit=%s\n' \
    "$(git -C "$vllm_root" rev-parse HEAD)" \
    "$(git -C "$kernel_root" rev-parse HEAD)" \
    "$(git -C "$repo_root" rev-parse HEAD)"
  printf 'target_revision=%s\ndraft_revision=%s\n' \
    4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb \
    5e07c246915c86dc6920fead03d019989224f2ba
  printf 'tp=4\nep=4\nmax_model_len=8192\nblock_size=64\nmax_num_seqs=1\n'
  printf 'benchmark_max_tokens=%s\n' "$max_tokens"
  printf 'execution_width=%s\nspeculative_depth=%s\nexact_target_path=true\n' \
    "$execution_width" "$speculative_depth"
  printf 'prebuilt_exact_metadata=%s\ngraph_topology=%s\n' \
    "$width12" "$expected_graph_topology"
  printf 'prefix_caching=false\nasync_scheduling=false\none_active_generation=true\n'
  printf 'suite_sha256=%s\nteacher_sha256=%s\n' "$expected_suite" \
    "$([[ -n "$teacher" ]] && sha256sum "$teacher" | awk '{print $1}' || echo none)"
  sha256sum "$0" "$server" "$scale_audit" "$benchmark" "$qualifier" "$comparator"
} > "$run_dir/identity.txt"

"$venv_python" "$idle_wrapper" --output "$run_dir/pre-idle.json"

server_pid=""
service_alive() {
  [[ -n "$server_pid" ]] \
    && (kill -0 "$server_pid" 2>/dev/null || kill -0 -- "-$server_pid" 2>/dev/null)
}
stop_service() {
  [[ -n "$server_pid" ]] || return 0
  local signal attempts
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
  local status="$?"
  trap - EXIT INT TERM
  set +e
  stop_service
  ! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null
  worker_status="$?"
  "$venv_python" "$idle_wrapper" --output "$run_dir/post-idle.json"
  idle_status="$?"
  if [[ -e "$rpc_dir" ]]; then mv -- "$rpc_dir" "$run_dir/rpc-after-stop"; fi
  printf 'original_status=%s\nworker_status=%s\nidle_status=%s\n' \
    "$status" "$worker_status" "$idle_status" > "$run_dir/cleanup-status.txt"
  chmod -R a-w -- "$run_dir" 2>/dev/null || true
  exit "$status"
}
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

setsid /usr/bin/env -i \
  PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  HOME="$run_dir/private-home" TMPDIR="$run_dir/private-tmp" \
  HF_HOME="$run_dir/private-cache/hf" HF_HUB_CACHE="$run_dir/private-cache/hf/hub" \
  TRANSFORMERS_CACHE="$run_dir/private-cache/hf/transformers" \
  VLLM_CACHE_ROOT="$run_dir/private-cache/vllm" \
  TORCHINDUCTOR_CACHE_DIR="$run_dir/private-cache/torchinductor" \
  TRITON_CACHE_DIR="$run_dir/private-cache/triton" \
  SYCL_CACHE_DIR="$run_dir/private-cache/sycl" \
  NUMBA_CACHE_DIR="$run_dir/private-cache/numba" \
  PYTHONPYCACHEPREFIX="$run_dir/private-cache/pycache" \
  XDG_CACHE_HOME="$run_dir/private-cache" \
  XDG_CONFIG_HOME="$run_dir/private-xdg/config" \
  XDG_DATA_HOME="$run_dir/private-xdg/data" \
  XDG_STATE_HOME="$run_dir/private-xdg/state" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  PYTHONHASHSEED=0 PYTHONPATH="$vllm_root:$kernel_root" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 \
  VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  LD_PRELOAD= ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 \
  ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 \
  FI_TCP_IFACE="$iface" CCL_KVS_IFACE="$iface" \
  TORCH_XCCL_ASYNC_ERROR_HANDLING=1 LD_LIBRARY_PATH="$native_library_path" \
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_LAGUNA_FP8_KV_SCALE_AUDIT=1 \
  VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS=0 \
  VLLM_XPU_EXACT_SPEC_ATTN=1 \
  VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 \
  VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 \
  VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 \
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0 \
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0 \
  VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 \
  VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK="$width12" \
  VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK="$width12" \
  VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE="$width12" \
  VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16="$width12" \
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
  LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=11 \
  VLLM_XPU_LAGUNA_EXACT_MAX_M=12 \
  VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH=0 \
  LAGUNA_M=12 LAGUNA_SPEC=11 LAGUNA_GPU_UTIL=0.90 \
  LAGUNA_LOCAL_ARGMAX=false VLLM_XPU_LAGUNA_CAPTURE_FILTER_DEBUG=1 \
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" \
  VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=0 \
  VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS=0 \
  VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA="$width12" \
  VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" \
  VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
  "$server" "$mode" "$run_dir" > "$run_dir/server.log" 2>&1 &
server_pid="$!"
printf '%s\n' "$server_pid" > "$run_dir/server.pid"

for _ in $(seq 1 180); do
  curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1 && break
  service_alive || die "service exited before health"
  sleep 5
done
curl -fsS http://127.0.0.1:18080/health >/dev/null \
  || die "service startup timed out"
tr '\0' '\n' < "/proc/$server_pid/environ" | LC_ALL=C sort \
  > "$run_dir/service-environment.txt"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-before-suite.prom"

cd "$repo_root"
"$venv_python" "$benchmark" \
  --base-url http://127.0.0.1:18080 \
  --model laguna-s-2.1-int4-fp8-kv \
  --suite experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json \
  --max-tokens "$max_tokens" --metric-tokens 100 --seed 1 --timeout 1800 \
  --return-token-ids \
  --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' \
  --out "$run_dir/bench.json" > "$run_dir/bench.stdout"
"$venv_python" "$qualifier" "$run_dir/bench.json" --in-place \
  > "$run_dir/metric-accounting.stdout"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-after-suite.prom"

jq -e --argjson max_tokens "$max_tokens" '
  .fresh_response_validity.valid == true
  and .fresh_response_validity.cached_tokens_all_zero == true
  and .realistic_final_gate.passed == true
  and .run_identity.prompt_count == 13
  and .run_identity.max_tokens == $max_tokens
  and .run_identity.seed == 1
' "$run_dir/bench.json" >/dev/null

[[ "$(grep -ac 'LAGUNA_FP8_KV_SCALE_AUDIT=PASS model=target layers=48' "$run_dir/server.log")" == 4 ]] \
  || die "target runtime scale audit did not pass on all four ranks"
# Backend selection uses logger.info_once and therefore appears once for the
# TP4 engine. Per-rank execution identity is independently proved by the four
# post-load scale-audit records above.
[[ "$(grep -ac 'Using Flash Attention backend' "$run_dir/server.log")" == 1 ]] \
  || die "Flash Attention backend selection marker is missing or duplicated"
grep -aq 'kv_cache_dtype=fp8' "$run_dir/server.log" \
  || die "engine did not resolve FP8 KV"
! grep -qaiE 'attention backend.*fallback|kv_cache_dtype not supported|scaling factor.*1\\.0.*target' \
  "$run_dir/server.log" || die "FP8 backend or target scale fallback detected"

if [[ "$mode" == candidate ]]; then
  [[ "$(grep -ac 'LAGUNA_FP8_KV_SCALE_AUDIT=PASS model=draft layers=6 scale_mode=unit_uncalibrated' "$run_dir/server.log")" == 4 ]] \
    || die "draft runtime scale classification did not pass on all four ranks"
  "$venv_python" "$comparator" \
    --teacher "$teacher" --require-text-hash \
    --candidate "$run_dir/bench.json" \
    --out "$run_dir/exactness-vs-fp8-q1.json" \
    > "$run_dir/exactness-vs-fp8-q1.stdout"
  jq -e '
    .all_exact == true
    and .candidates[0].comparison.exact_count == 13
    and .candidates[0].comparison.total == 13
    and .candidates[0].comparison.all_cached_zero == true
    and .candidates[0].comparison.text_sha256_checked_count == 13
    and .candidates[0].comparison.all_text_sha256_equal == true
  ' "$run_dir/exactness-vs-fp8-q1.json" >/dev/null
  "$venv_python" - "$run_dir/server.log" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
rank = re.compile(r"Worker_TP([0-3])_EP([0-3])")
expected = {(0, 0), (1, 1), (2, 2), (3, 3)}
for marker in ("Captured", "Replayed"):
    rows = [line for line in lines if f"{marker} audited breakable cudagraph" in line]
    observed = {
        tuple(map(int, match.groups()))
        for line in rows
        if (match := rank.search(line))
    }
    if len(rows) != 4 or observed != expected:
        raise SystemExit(f"{marker} graph ranks mismatch: rows={len(rows)} {observed}")
    if any("(graphs=146, eager_breaks=145)" not in line for line in rows):
        raise SystemExit(f"{marker} graph topology is not 146/145")
PY
fi

stop_service
server_pid=""
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null \
  || die "workers survived shutdown"
"$venv_python" "$idle_wrapper" --output "$run_dir/post-idle.json"
mv -- "$rpc_dir" "$run_dir/rpc-after-stop"
printf 'status=PASS\n' > "$run_dir/status.txt"
trap - EXIT INT TERM
chmod -R a-w -- "$run_dir"
echo "Laguna FP8 KV $mode PASS: $run_dir"
