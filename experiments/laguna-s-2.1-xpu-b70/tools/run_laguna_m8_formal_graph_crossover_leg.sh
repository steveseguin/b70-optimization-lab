#!/usr/bin/env bash
# One sealed A1/B1/B2/A2 formal Laguna M8 eager-vs-Breakable-graph leg.
# No warmup is performed.  The caller must execute the four legs sequentially.
set -euo pipefail
umask 077

readonly frozen_path=/home/steve/.venvs/deepseek-v4-xpu/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH="$frozen_path"
export PYTHONDONTWRITEBYTECODE=1

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=laguna_nvme_paths.sh
source "$script_dir/laguna_nvme_paths.sh"

treatment="${1:?usage: run_laguna_m8_formal_graph_crossover_leg.sh eager|graph A1|B1|B2|A2 RUN_DIR}"
label="${2:?usage: run_laguna_m8_formal_graph_crossover_leg.sh eager|graph A1|B1|B2|A2 RUN_DIR}"
run_dir="${3:?usage: run_laguna_m8_formal_graph_crossover_leg.sh eager|graph A1|B1|B2|A2 RUN_DIR}"

readonly repo_root=/home/steve/llm-optimizations
readonly vllm_root=/home/steve/src/laguna-vllm-runtime-graph-20260724
readonly kernel_root=/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc
readonly venv_python=/home/steve/.venvs/deepseek-v4-xpu/bin/python
readonly vllm_binary=/home/steve/.venvs/deepseek-v4-xpu/bin/vllm
readonly graph_serve="$script_dir/serve_laguna_m8_breakable_graph_nvme.sh"
readonly eager_serve="$script_dir/serve_laguna_m8_eager_nvme.sh"
readonly comparator="$script_dir/compare_exact_runs.py"
readonly benchmark="$repo_root/scripts/bench-openai-realistic-suite.py"
readonly idle_wrapper="$script_dir/capture_laguna_m8_idle_snapshot.py"
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
readonly expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
readonly expected_vllm_binary=d16721cbe3e6bef44881b6b45ce64d9362a82bec4748754bd91ec85704c243fb
readonly expected_target_config=9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
readonly expected_draft_config=6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
readonly rpc_dir="$LAGUNA_NVME_TMP_ROOT/m8fc-${label,,}"

case "$treatment:$label" in
  eager:A1|eager:A2|graph:B1|graph:B2) ;;
  *) echo "formal label/treatment must be eager:A1, graph:B1, graph:B2, or eager:A2" >&2; exit 2 ;;
esac
(( $# == 3 )) || { echo "exactly three arguments are required" >&2; exit 2; }

die() { echo "Laguna formal M8 crossover leg: $*" >&2; exit 2; }
check_hash() { [[ "$(sha256sum -- "$1" | awk '{print $1}')" == "$2" ]] || die "SHA256 drift: $1"; }

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "run directory must be below fixed NVMe run root"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run directory must be canonical"
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited runtime variables: $ambient_sensitive"
for path in "$vllm_root" "$kernel_root" "$graph_serve" "$eager_serve" "$comparator" "$benchmark" "$idle_wrapper" "$suite" "$teacher"; do
  [[ -e "$path" && "$(realpath -e -- "$path")" != /media/* ]] || die "missing or USB-resident required path: $path"
done
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
[[ "$(git -C "$vllm_root" rev-parse HEAD)" == "$expected_vllm" ]] || die "vLLM commit drift"
[[ "$(git -C "$kernel_root" rev-parse HEAD)" == "$expected_kernels" ]] || die "kernel commit drift"
git -C "$vllm_root" merge-base --is-ancestor "$record_vllm" "$expected_vllm" \
  || die "vLLM is not an approved-record descendant"
git -C "$kernel_root" merge-base --is-ancestor "$record_kernels" "$expected_kernels" \
  || die "kernels are not an approved-record descendant"
check_hash "$suite" "$expected_suite"; check_hash "$teacher" "$expected_teacher"
check_hash "$comparator" "$expected_comparator"; check_hash "$benchmark" "$expected_benchmark"
check_hash "$venv_python" "$expected_python"; check_hash "$vllm_binary" "$expected_vllm_binary"
check_hash "$LAGUNA_NVME_TARGET_ROOT/config.json" "$expected_target_config"
check_hash "$LAGUNA_NVME_DRAFT_ROOT/config.json" "$expected_draft_config"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" \
  126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" \
  f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" \
  6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96
laguna_nvme_verify_model_contents
[[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "refusing reused RPC path"
! ss -H -ltn 'sport = :18080' | grep -q . || die "port 18080 already has a listener"
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || die "existing vLLM workers block leg"

laguna_nvme_prepare_run_dir "$run_dir"
chmod 700 -- "$run_dir"
mkdir --mode=700 "$rpc_dir"
mkdir -p "$run_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state},idle-interval}
chmod -R 700 -- "$run_dir"

capture_idle() { "$venv_python" "$idle_wrapper" --output "$1"; }
verify_idle_interval() {
  local phase="$1" started elapsed index
  started="$(date +%s)"
  for index in $(seq -w 0 12); do
    capture_idle "$run_dir/idle-interval/${phase}-${index}.json" || return 1
    [[ "$index" == 12 ]] || sleep 5
  done
  elapsed=$(( $(date +%s) - started ))
  (( elapsed >= 60 )) || die "verified idle interval was only ${elapsed}s"
  printf '%s elapsed_seconds=%s snapshots=13\n' "$phase" "$elapsed" >> "$run_dir/idle-interval/summary.txt"
}
assert_no_workers() {
  ! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || return 1
  ! ss -H -ltn 'sport = :18080' | grep -q .
}
server_pid=""
service_alive() { [[ -n "$server_pid" ]] && (kill -0 "$server_pid" 2>/dev/null || kill -0 -- "-$server_pid" 2>/dev/null); }
stop_service() {
  local signal attempts
  [[ -n "$server_pid" ]] || return 0
  for signal in INT TERM KILL; do
    service_alive || break
    kill "-$signal" -- "-$server_pid" 2>/dev/null || true; kill "-$signal" "$server_pid" 2>/dev/null || true
    case "$signal" in INT) attempts=30 ;; TERM) attempts=15 ;; KILL) attempts=10 ;; esac
    for _ in $(seq 1 "$attempts"); do service_alive || break; sleep 1; done
  done
  wait "$server_pid" 2>/dev/null || true
  ! service_alive
}
finalize() {
  local status="$?" stop_status=0 worker_status=0 idle_status=0
  trap - EXIT INT TERM; set +e
  stop_service || stop_status=1
  assert_no_workers || worker_status=1
  capture_idle "$run_dir/failure-post-idle.json" || idle_status=1
  printf 'original_status=%s\nstop_status=%s\nworker_status=%s\nidle_status=%s\n' "$status" "$stop_status" "$worker_status" "$idle_status" > "$run_dir/cleanup-status.txt"
  chmod -R a-w -- "$run_dir" "$rpc_dir" 2>/dev/null || true
  exit "$status"
}
trap finalize EXIT; trap 'exit 130' INT; trap 'exit 143' TERM

capture_idle "$run_dir/pre-idle.json"
verify_idle_interval prestart
{
  printf 'schema=laguna-m8-formal-graph-crossover-leg-v1\nlabel=%s\ntreatment=%s\n' "$label" "$treatment"
  printf 'vllm_commit=%s\nkernel_commit=%s\nmodel=%s\ndraft=%s\nmodel_manifest_sha256=%s\n' "$expected_vllm" "$expected_kernels" "$LAGUNA_NVME_TARGET_ROOT" "$LAGUNA_NVME_DRAFT_ROOT" "$LAGUNA_NVME_MANIFEST_SHA256"
  printf 'suite_sha256=%s\nteacher_sha256=%s\nselector_stack=exact-m8-dflash7-w1routew2-routeinterleave-shared-elementwise-qknormrope-n64\n' "$expected_suite" "$expected_teacher"
  printf 'graph_only_difference=%s\nno_warmup=true\nverified_idle_interval_seconds=60\n' "$treatment"
  sha256sum "$0" "$graph_serve" "$eager_serve" "$comparator" "$benchmark" "$idle_wrapper" "$venv_python" "$vllm_binary"
} > "$run_dir/identity.txt"

if [[ "$treatment" == graph ]]; then graph=1; serve_script="$graph_serve"; else graph=0; serve_script="$eager_serve"; fi
setsid /usr/bin/env -i \
  PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 HOME="$run_dir/private-home" TMPDIR="$run_dir/private-tmp" \
  HF_HOME="$run_dir/private-cache/hf" HF_HUB_CACHE="$run_dir/private-cache/hf/hub" TRANSFORMERS_CACHE="$run_dir/private-cache/hf/transformers" VLLM_CACHE_ROOT="$run_dir/private-cache/vllm" TORCHINDUCTOR_CACHE_DIR="$run_dir/private-cache/torchinductor" TRITON_CACHE_DIR="$run_dir/private-cache/triton" SYCL_CACHE_DIR="$run_dir/private-cache/sycl" NUMBA_CACHE_DIR="$run_dir/private-cache/numba" PYTHONPYCACHEPREFIX="$run_dir/private-cache/pycache" XDG_CACHE_HOME="$run_dir/private-cache" XDG_CONFIG_HOME="$run_dir/private-xdg/config" XDG_DATA_HOME="$run_dir/private-xdg/data" XDG_STATE_HOME="$run_dir/private-xdg/state" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 PYTHONPATH="$vllm_root:$kernel_root" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD= ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE=eno1 CCL_KVS_IFACE=eno1 TORCH_XCCL_ASYNC_ERROR_HANDLING=1 LD_LIBRARY_PATH="/home/steve/.venvs/deepseek-v4-xpu/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib" \
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1 VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1 VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0 VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7 VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
  "$serve_script" "$run_dir" >"$run_dir/server.log" 2>&1 &
server_pid="$!"; printf '%s\n' "$server_pid" > "$run_dir/server.pid"
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1 && break; service_alive || die "service exited before health"; sleep 5; done
curl -fsS http://127.0.0.1:18080/health >/dev/null || die "service startup timed out"
tr '\0' '\n' < "/proc/$server_pid/environ" | LC_ALL=C sort > "$run_dir/service-environment.txt"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-before-suite.prom"
cd "$repo_root"
"$venv_python" "$benchmark" --base-url http://127.0.0.1:18080 --model laguna-s-2.1-int4 --suite experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 1800 --return-token-ids --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' --out "$run_dir/bench.json" > "$run_dir/bench.stdout"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-after-suite.prom"
"$venv_python" "$comparator" --teacher "$teacher" --candidate "$run_dir/bench.json" --out "$run_dir/exactness-vs-q1.json" > "$run_dir/exactness-vs-q1.stdout"
jq -e '.fresh_response_validity.valid == true and .fresh_response_validity.each_prompt_run_once == true and .fresh_response_validity.cached_tokens_all_zero == true and .realistic_final_gate.passed == true and .run_identity.prompt_count == 13 and .run_identity.max_tokens == 512 and .run_identity.seed == 1' "$run_dir/bench.json" >/dev/null
jq -e '.all_exact == true and .candidates[0].comparison.exact_count == 13 and .candidates[0].comparison.total == 13 and .candidates[0].comparison.all_cached_zero == true' "$run_dir/exactness-vs-q1.json" >/dev/null
if [[ "$treatment" == graph ]]; then
  "$venv_python" - "$run_dir/server.log" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
captures = [line for line in lines if "Captured audited breakable cudagraph" in line]
replays = [line for line in lines if "Replayed audited breakable cudagraph" in line]
rank = re.compile(r"Worker_TP([0-3])_EP([0-3])")
expected = {(0, 0), (1, 1), (2, 2), (3, 3)}
for name, rows in (("capture", captures), ("replay", replays)):
    observed = {tuple(map(int, match.groups())) for line in rows if (match := rank.search(line))}
    if len(rows) != 4 or observed != expected:
        raise SystemExit(f"graph {name} topology mismatch: rows={len(rows)} ranks={sorted(observed)}")
    if not all("BreakableCUDAGraphCapture(graphs=146, eager_breaks=145)" in line for line in rows):
        raise SystemExit(f"graph {name} lacks the audited 146/145 topology")
PY
fi
stop_service; server_pid=""
assert_no_workers || die "workers or listener survived shutdown"
capture_idle "$run_dir/post-idle.json"
verify_idle_interval poststop
mv -- "$rpc_dir" "$run_dir/rpc-after-stop"
printf 'status=PASS\n' > "$run_dir/status.txt"
echo "Laguna formal M8 crossover leg PASS: $label $treatment $run_dir"
