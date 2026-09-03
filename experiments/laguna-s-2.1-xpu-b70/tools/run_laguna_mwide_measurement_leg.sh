#!/usr/bin/env bash
# One sealed Laguna M8 Breakable-graph metadata control/candidate leg.
# No warmup is performed.  The caller must execute the four legs sequentially.
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly venv_root="${REPRO_VENV_ROOT:-/home/steve/.venvs/deepseek-v4-xpu}"
readonly frozen_path="$venv_root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH="$frozen_path"
export PYTHONDONTWRITEBYTECODE=1

readonly nvme_paths="$script_dir/laguna_nvme_paths.sh"
# shellcheck source=laguna_nvme_paths.sh
source "$nvme_paths"

treatment="${1:?usage: run_laguna_m8_metadata_formal_crossover_leg.sh control|candidate A1|B1|B2|A2 RUN_DIR}"
label="${2:?usage: run_laguna_m8_metadata_formal_crossover_leg.sh control|candidate A1|B1|B2|A2 RUN_DIR}"
run_dir="${3:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA}"
readonly laguna_m="${4:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA}"
readonly laguna_spec="${5:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA}"
readonly metadata_arg="${6:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA DRAFTGRAPH}"
# 0 leaves the drafter eager, as every record run to date has. 1 captures it
# in its own breakable graph; the target's audited topology is unaffected
# because the two wrappers are independent instances.
readonly draft_graph="${7:?usage: TREATMENT LABEL RUN_DIR M SPEC METADATA DRAFTGRAPH [FUSIONS]}"
# The exact shared-elementwise and QKNorm/RoPE fusions, on by default. They are
# separable so a width can be measured with and without them, which is the only
# way to attribute a failure at a new width to the width or to the fusions.
readonly fusions="${8:-1}"
# QKNorm/RoPE is separable from shared-elementwise because only its launcher
# maps work-groups onto whole heads. With the target's 48 attention heads that
# is H=14 per TP4 rank, so rows*H divides HEADS_PER_WG at 8 and 16 but not at
# 12. Shared-elementwise has no such constraint, so the two are controlled
# independently and width 12 can use the half that is reachable.
readonly qknorm="${9:-$fusions}"
# Vocab-parallel local argmax in the drafter. The draft head is a ParallelLMHead
# over a 100352-token vocabulary, so the default path all-gathers roughly 4.8 MB
# of logits every cycle across a PCIe-connected TP4 group; this exchanges
# (value, index) pairs instead. It must select the same token, which the leg's
# bitwise gate decides.
readonly local_argmax="${10:-0}"
# Capture each of the 48 target attention boundaries as its own XPU subgraph.
# This remains default-off and is mutually exclusive with the prebuilt metadata
# experiment until their combination is validated separately.
readonly capture_attention="${11:-0}"
# Record each target attention body directly into its surrounding outer graph,
# retiring the 48 attention breaks while preserving all 97 collective breaks.
# This is a separate treatment from nested attention subgraphs and requires the
# proven persistent exact-attention metadata path.
readonly inline_attention="${12:-0}"
# Exact width-12 router plus DFlash context-KV workspace stack. The control
# uses the same source and candidate native binary with this selector off.
readonly width12_stack="${13:-0}"
# Draft-only per-channel FP8 W8A16 projections, independent FP8 draft LM head,
# and the exact auxiliary-combine workspace. This is valid only on top of the
# complete width-12 stack and leaves the target model and verifier unchanged.
readonly dflash_fp8="${14:-0}"

readonly repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"

readonly vllm_root="${REPRO_VLLM_TREE:-/home/steve/src/laguna-vllm-width12-stack-clean-20260726}"
readonly kernel_root="${REPRO_KERNEL_TREE:-/home/steve/src/laguna-xpu-kernels-width12-router-clean-20260726}"
readonly venv_python="$venv_root/bin/python"
readonly vllm_binary="$venv_root/bin/vllm"
readonly repro_root="$repo_root/repro/laguna-s-2.1-int4-b70-102tps-20260726"
readonly runtime_lock="${REPRO_RUNTIME_LOCK:-$repro_root/manifests/runtime-lock.json}"
readonly runtime_verifier="${REPRO_RUNTIME_VERIFIER:-$repro_root/verify-runtime.py}"
readonly model_release_manifest="${REPRO_MODEL_MANIFEST:-$repro_root/manifests/model-release-files.sha256}"
readonly xpumem_module="${REPRO_XPUMEM_MODULE:-/home/steve/src/deepseek-v4-xpu-kernels-qnorm-routeportfolio/vllm_xpu_kernels/xpumem_allocator.abi3.so}"
readonly kernel_package="$kernel_root/vllm_xpu_kernels"
readonly native_library_path="$kernel_package:$venv_root/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib"
readonly graph_serve="$script_dir/serve_laguna_mwide_graph_nvme.sh"
readonly comparator="$script_dir/compare_exact_runs.py"
readonly benchmark="$repo_root/scripts/bench-openai-realistic-suite.py"
readonly metric_qualifier="$repo_root/scripts/qualify_realistic_window_metrics.py"
readonly idle_wrapper="$script_dir/capture_laguna_m8_idle_snapshot.py"
readonly suite="$repo_root/experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
readonly teacher="${REPRO_TEACHER:-$LAGUNA_NVME_RUN_ROOT/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json}"
readonly teacher_text_oracle="${REPRO_TEACHER_TEXT_ORACLE:-}"
readonly expected_vllm="$(git -C "$vllm_root" rev-parse HEAD)"
readonly expected_kernels="$(git -C "$kernel_root" rev-parse HEAD)"
readonly expected_suite=9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638
readonly expected_teacher="${REPRO_TEACHER_SHA256:-d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1}"
readonly expected_teacher_text_oracle="${REPRO_TEACHER_TEXT_ORACLE_SHA256:-}"
readonly expected_comparator=c18b6f37aa0f5a848a9d771fa91de14bab115b41557b9d7066bce5984c2a6945
readonly expected_benchmark=40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a
readonly expected_metric_qualifier=3f930c1789a468873b23181353c77c7f8ba875db8415b409670f034e9ca92b20
readonly expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8
readonly expected_vllm_binary=d16721cbe3e6bef44881b6b45ce64d9362a82bec4748754bd91ec85704c243fb
readonly expected_target_config=9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6
readonly expected_draft_config=6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926
readonly expected_runtime_lock=8c861e5c9d44232346770e2822aa795179f8f90c2678d2ebbb42a690ef4f4a97
readonly expected_runtime_verifier=e43f3c9f46e299eeaa8d7bbc828fadeec2ae60f69f39529f7130f154d158f20d
readonly expected_model_release_manifest=c19edb79458a24ceb4bb26c991302de71ef29be40e70124e90bf6c13538c692e
readonly rpc_dir="$LAGUNA_NVME_TMP_ROOT/m8mc-${label,,}"

case "$treatment:$label" in
  control:A1|control:A2|candidate:B1|candidate:B2) ;;
  *) echo "formal label/treatment must be control:A1, candidate:B1, candidate:B2, or control:A2" >&2; exit 2 ;;
esac
(( $# >= 7 && $# <= 14 )) || { echo "seven to fourteen arguments are required" >&2; exit 2; }
case "$draft_graph" in 0|1) ;; *) echo "DRAFTGRAPH must be 0 or 1" >&2; exit 2 ;; esac
case "$metadata_arg" in 0|1) ;; *) echo "METADATA must be 0 or 1" >&2; exit 2 ;; esac
case "$fusions" in 0|1) ;; *) echo "FUSIONS must be 0 or 1" >&2; exit 2 ;; esac
case "$qknorm" in 0|1) ;; *) echo "QKNORM must be 0 or 1" >&2; exit 2 ;; esac
case "$local_argmax" in 0|1) ;; *) echo "LOCAL_ARGMAX must be 0 or 1" >&2; exit 2 ;; esac
case "$capture_attention" in 0|1) ;; *) echo "CAPTURE_ATTENTION must be 0 or 1" >&2; exit 2 ;; esac
case "$inline_attention" in 0|1) ;; *) echo "INLINE_ATTENTION must be 0 or 1" >&2; exit 2 ;; esac
case "$width12_stack" in 0|1) ;; *) echo "WIDTH12_STACK must be 0 or 1" >&2; exit 2 ;; esac
case "$dflash_fp8" in 0|1) ;; *) echo "DFLASH_FP8 must be 0 or 1" >&2; exit 2 ;; esac
(( capture_attention == 0 || metadata_arg == 0 )) \
  || { echo "CAPTURE_ATTENTION=1 requires METADATA=0" >&2; exit 2; }
(( capture_attention == 0 || inline_attention == 0 )) \
  || { echo "CAPTURE_ATTENTION and INLINE_ATTENTION are mutually exclusive" >&2; exit 2; }
(( inline_attention == 0 || metadata_arg == 1 )) \
  || { echo "INLINE_ATTENTION=1 requires METADATA=1" >&2; exit 2; }
(( width12_stack == 0 || (laguna_m == 12 && laguna_spec == 11) )) \
  || { echo "WIDTH12_STACK=1 requires M=12 and SPEC=11" >&2; exit 2; }
[[ "$width12_stack" == 0 || "$treatment" == candidate ]] \
  || { echo "WIDTH12_STACK=1 requires candidate treatment" >&2; exit 2; }
(( dflash_fp8 == 0 || width12_stack == 1 )) \
  || { echo "DFLASH_FP8=1 requires WIDTH12_STACK=1" >&2; exit 2; }
[[ "$dflash_fp8" == 0 || "$treatment" == candidate ]] \
  || { echo "DFLASH_FP8=1 requires candidate treatment" >&2; exit 2; }

die() { echo "Laguna formal M8 crossover leg: $*" >&2; exit 2; }

# The interface carrying the cluster IP is resolved at runtime, not hardcoded.
# A reboot on 2026-07-26 swapped the onboard NIC names: the port holding
# 10.0.0.65 (MAC 3c:ec:ef:ce:5a:7e) moved from eno1 to eth1, and a different
# port took the name eno1 and stayed down. oneCCL then failed with
# "can't find interface eno1 to get host IP", which aborts KVS and PMI
# bootstrap before any GPU transport is created. Deriving the name keeps the
# harness correct across renames. This affects only CCL's rendezvous, not the
# GPU data path.
laguna_cluster_iface() {
  local ip="${REPRO_CLUSTER_IP:-${LAGUNA_CLUSTER_IP:-10.0.0.65}}" iface
  iface="$(ip -o -4 addr show 2>/dev/null | awk -v ip="$ip" '$4 ~ "^"ip"/" {print $2; exit}')"
  [[ -n "$iface" ]] || { echo "no interface carries $ip" >&2; return 1; }
  [[ "$(cat "/sys/class/net/$iface/operstate" 2>/dev/null)" == up ]] \
    || { echo "interface $iface carrying $ip is not up" >&2; return 1; }
  printf '%s\n' "$iface"
}

check_hash() { [[ "$(sha256sum -- "$1" | awk '{print $1}')" == "$2" ]] || die "SHA256 drift: $1"; }

[[ "$run_dir" == "$LAGUNA_NVME_RUN_ROOT"/* ]] || die "run directory must be below fixed NVMe run root"
[[ "$(realpath -m -- "$run_dir")" == "$run_dir" ]] || die "run directory must be canonical"
cluster_iface="$(laguna_cluster_iface)" || die "cannot resolve the cluster interface"
readonly cluster_iface
laguna_nvme_prepare_paths
laguna_nvme_assert_fresh_run_path "$run_dir"
ambient_sensitive="$(compgen -e | LC_ALL=C sort -u | awk '/^(VLLM|LAGUNA|XPU_GRAPH$|ZE_|ZES_|SYCL|UR_|CCL_|FI_|I_MPI_|PSM|OMP_|MKL_|KMP_|ONEAPI_|INTEL_|IGC_|NEO|IPEX_|TORCH|PYTORCH_|TRITON_|LD_)/ {print}')"
[[ -z "$ambient_sensitive" ]] || die "refusing inherited runtime variables: $ambient_sensitive"
for path in \
  "$vllm_root" "$kernel_root" "$graph_serve" "$nvme_paths" "$comparator" \
  "$benchmark" "$metric_qualifier" "$idle_wrapper" "$suite" "$teacher" \
  "$runtime_lock" "$runtime_verifier" "$model_release_manifest" \
  "$xpumem_module"; do
  [[ -e "$path" && "$(realpath -e -- "$path")" != /media/* ]] || die "missing or USB-resident required path: $path"
done
if [[ -n "$teacher_text_oracle" ]]; then
  [[ -n "$expected_teacher_text_oracle" ]] \
    || die "REPRO_TEACHER_TEXT_ORACLE_SHA256 is required with the text oracle"
  [[ -f "$teacher_text_oracle" ]] || die "missing text oracle: $teacher_text_oracle"
  check_hash "$teacher_text_oracle" "$expected_teacher_text_oracle"
fi
[[ -z "$(git -C "$repo_root" status --short)" ]] || die "main worktree is dirty"
[[ -z "$(git -C "$vllm_root" status --short)" ]] || die "vLLM worktree is dirty"
[[ -z "$(git -C "$kernel_root" status --short)" ]] || die "kernel worktree is dirty"
check_hash "$suite" "$expected_suite"; check_hash "$teacher" "$expected_teacher"
check_hash "$comparator" "$expected_comparator"
check_hash "$benchmark" "$expected_benchmark"
check_hash "$metric_qualifier" "$expected_metric_qualifier"
check_hash "$runtime_lock" "$expected_runtime_lock"
check_hash "$runtime_verifier" "$expected_runtime_verifier"
check_hash "$model_release_manifest" "$expected_model_release_manifest"
check_hash "$venv_python" "$expected_python"
check_hash "$vllm_binary" "$expected_vllm_binary"
check_hash "$LAGUNA_NVME_TARGET_ROOT/config.json" "$expected_target_config"
check_hash "$LAGUNA_NVME_DRAFT_ROOT/config.json" "$expected_draft_config"
check_hash "$kernel_root/vllm_xpu_kernels/_C.abi3.so" \
  126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2
check_hash "$kernel_root/vllm_xpu_kernels/_xpu_C.abi3.so" \
  f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8
check_hash "$kernel_root/vllm_xpu_kernels/_moe_C.abi3.so" \
  00fd81608f057039d31e1b316fecbecec60b3b03151e66b95d0f844185119715
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_2.so" \
  fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96
check_hash "$kernel_root/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
  3390a3065de25e06dbe95a8fbc2c8456c3489a2295816782e90a4086aedc9dd4
check_hash "$kernel_root/vllm_xpu_kernels/libattn_kernels_xe_2.so" \
  ad0eb26f3b0680fcd54a50de821e9c881524d50ad5361b872f88cb0b333b65ca
check_hash "$kernel_root/vllm_xpu_kernels/libgrouped_gemm_xe_default.so" \
  982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c
check_hash "$kernel_root/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so" \
  cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb
check_hash "$kernel_root/vllm_xpu_kernels/libmqa_logits_kernels_xe_2.so" \
  58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb
check_hash "$kernel_root/vllm_xpu_kernels/libmhc_kernels_xe_2.so" \
  f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f
check_hash "$xpumem_module" \
  8981f5e312cfab901a5bfa8e40a5a1f194e65db3a207784bfa602e5901e5a1a8
laguna_nvme_verify_model_contents
[[ ! -e "$rpc_dir" && ! -L "$rpc_dir" ]] || die "refusing reused RPC path"
! ss -H -ltn 'sport = :18080' | grep -q . || die "port 18080 already has a listener"
! pgrep -f 'vllm serve|VLLM::EngineCore|VLLM::Worker' >/dev/null 2>&1 || die "existing vLLM workers block leg"

laguna_nvme_prepare_run_dir "$run_dir"
chmod 700 -- "$run_dir"
mkdir --mode=700 "$rpc_dir"
mkdir -p "$run_dir"/{private-home,private-tmp,private-cache/{hf,vllm,torchinductor,triton,sycl,numba,pycache},private-xdg/{config,data,state},idle-interval}
chmod -R 700 -- "$run_dir"
/usr/bin/env -i \
  PATH="$frozen_path" \
  LANG=C.UTF-8 \
  LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 \
  PYTHONSAFEPATH=1 \
  PYTHONPATH="$vllm_root:$kernel_root" \
  LD_LIBRARY_PATH="$native_library_path" \
  "$venv_python" "$runtime_verifier" \
  --lock "$runtime_lock" \
  --vllm-tree "$vllm_root" \
  --kernel-tree "$kernel_root" \
  --venv-root "$venv_root" \
  --xpumem-module "$xpumem_module" \
  --json-out "$run_dir/runtime-verification.json" \
  > "$run_dir/runtime-verification.stdout"

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
  # Move the RPC directory under the failed run rather than leaving it in the
  # shared tmp root. It stays as evidence, and the path is freed so a retry at
  # the same label is not blocked by the reused-path guard -- which is an
  # integrity check against cross-run contamination, not a reason to require
  # manual cleanup after every failure.
  if [[ -e "$rpc_dir" && ! -e "$run_dir/rpc-after-stop" ]]; then
    mv -- "$rpc_dir" "$run_dir/rpc-after-failure" 2>/dev/null ||
      rm -rf -- "$rpc_dir" 2>/dev/null || true
  fi
  chmod -R a-w -- "$run_dir" 2>/dev/null || true
  exit "$status"
}
trap finalize EXIT; trap 'exit 130' INT; trap 'exit 143' TERM

# The shared-elementwise and QKNorm/RoPE fusion kernels were pinned to eight
# rows and so had to be disabled at other widths. They now take the row count at
# runtime, so they are enabled at every width and the flags are recorded in
# identity.txt alongside the width.
se="$fusions"; qk="$qknorm"; gpu_util=0.90
metadata_selector="$metadata_arg"
expected_num_graphs="$(( inline_attention == 1 ? 98 : 146 ))"
expected_num_eager_breaks="$(( inline_attention == 1 ? 97 : 145 ))"
capture_idle "$run_dir/pre-idle.json"
verify_idle_interval prestart
{
  printf 'schema=laguna-mwide-measurement-leg-v2\nlabel=%s\ntreatment=%s\n' "$label" "$treatment"
  printf 'exact_max_m=%s\nnum_speculative_tokens=%s\nprebuilt_exact_attn_metadata=%s\n' "$laguna_m" "$laguna_spec" "$metadata_arg"
  printf 'draft_breakable_graph=%s\ncluster_iface=%s\nlocal_argmax=%s\n' "$draft_graph" "$cluster_iface" "$local_argmax"
  printf 'capture_attention_graphs=%s\ninline_attention_graphs=%s\n' "$capture_attention" "$inline_attention"
  printf 'width12_router_workspace_stack=%s\nmwide_bf16_router_topk=%s\ndflash_context_kv_workspace=%s\n' "$width12_stack" "$width12_stack" "$width12_stack"
  printf 'dflash_fp8_w8a16=%s\ndflash_fp8_target_unchanged=true\n' "$dflash_fp8"
  printf 'm8_shared_elementwise=%s\nm8_qknorm_rope=%s\ngpu_memory_utilization=%s\n' "$se" "$qk" "$gpu_util"
  printf 'identity_source=actual_worktree_heads\nmeasurement_leg_not_record_leg=true\nvllm_commit=%s\nkernel_commit=%s\nmodel=%s\ndraft=%s\nmodel_manifest_sha256=%s\n' "$expected_vllm" "$expected_kernels" "$LAGUNA_NVME_TARGET_ROOT" "$LAGUNA_NVME_DRAFT_ROOT" "$LAGUNA_NVME_MANIFEST_SHA256"
  printf 'model_release_manifest_sha256=%s\nruntime_lock_sha256=%s\nruntime_verifier_sha256=%s\n' "$expected_model_release_manifest" "$expected_runtime_lock" "$expected_runtime_verifier"
  printf 'runtime_verification_sha256=%s\nxpumem_module_sha256=%s\n' "$(sha256sum "$run_dir/runtime-verification.json" | awk '{print $1}')" "$(sha256sum "$xpumem_module" | awk '{print $1}')"
  printf 'shared_native_module_sha256=%s\nxpu_native_module_sha256=%s\nmoe_native_module_sha256=%s\ngrouped_gemm_native_module_sha256=%s\n' "$(sha256sum "$kernel_package/_C.abi3.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/_xpu_C.abi3.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/_moe_C.abi3.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libgrouped_gemm_xe_2.so" | awk '{print $1}')"
  printf 'fa2_binary_sha256=%s\n' "$(sha256sum "$kernel_root/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" | awk '{print $1}')"
  printf 'attn_library_sha256=%s\n' "$(sha256sum "$kernel_root/vllm_xpu_kernels/libattn_kernels_xe_2.so" | awk '{print $1}')"
  printf 'grouped_gemm_default_sha256=%s\ngdn_attn_library_sha256=%s\nmqa_logits_library_sha256=%s\nmhc_library_sha256=%s\n' "$(sha256sum "$kernel_package/libgrouped_gemm_xe_default.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libgdn_attn_kernels_xe_2.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libmqa_logits_kernels_xe_2.so" | awk '{print $1}')" "$(sha256sum "$kernel_package/libmhc_kernels_xe_2.so" | awk '{print $1}')"
  printf 'suite_sha256=%s\nteacher_sha256=%s\nteacher_text_oracle_sha256=%s\nselector_stack=exact-m%s-dflash%s-breakablegraph-w1routew2-routeinterleave-n64-routerworkspace%s-draftfp8%s\n' "$expected_suite" "$expected_teacher" "${expected_teacher_text_oracle:-embedded-in-teacher}" "$laguna_m" "$laguna_spec" "$width12_stack" "$dflash_fp8"
  printf 'metadata_selector=%s\nattention_capture_selector=%s\ninline_attention_selector=%s\n' "$metadata_selector" "$capture_attention" "$inline_attention"
  printf 'expected_num_graphs=%s\nexpected_num_eager_breaks=%s\n' "$expected_num_graphs" "$expected_num_eager_breaks"
  printf 'no_warmup=true\nsuite_invocations=1\nretries=0\nverified_idle_interval_seconds=60\n'
  sha256sum "$0" "$graph_serve" "$nvme_paths" "$comparator" "$benchmark" "$metric_qualifier" "$idle_wrapper" "$venv_python" "$vllm_binary"
} > "$run_dir/identity.txt"

graph=1
serve_script="$graph_serve"
setsid /usr/bin/env -i \
  PATH="$frozen_path" LANG=C.UTF-8 LC_ALL=C.UTF-8 HOME="$run_dir/private-home" TMPDIR="$run_dir/private-tmp" \
  HF_HOME="$run_dir/private-cache/hf" HF_HUB_CACHE="$run_dir/private-cache/hf/hub" TRANSFORMERS_CACHE="$run_dir/private-cache/hf/transformers" VLLM_CACHE_ROOT="$run_dir/private-cache/vllm" TORCHINDUCTOR_CACHE_DIR="$run_dir/private-cache/torchinductor" TRITON_CACHE_DIR="$run_dir/private-cache/triton" SYCL_CACHE_DIR="$run_dir/private-cache/sycl" NUMBA_CACHE_DIR="$run_dir/private-cache/numba" PYTHONPYCACHEPREFIX="$run_dir/private-cache/pycache" XDG_CACHE_HOME="$run_dir/private-cache" XDG_CONFIG_HOME="$run_dir/private-xdg/config" XDG_DATA_HOME="$run_dir/private-xdg/data" XDG_STATE_HOME="$run_dir/private-xdg/state" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONHASHSEED=0 PYTHONPATH="$vllm_root:$kernel_root" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 VLLM_NO_USAGE_STATS=1 VLLM_RPC_BASE_PATH="$rpc_dir" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 LD_PRELOAD= ONEAPI_DEVICE_SELECTOR=level_zero:0,1,2,3 ZE_AFFINITY_MASK=0,1,2,3 CCL_ATL_TRANSPORT=ofi CCL_TOPO_P2P_ACCESS=1 FI_TCP_IFACE="$cluster_iface" CCL_KVS_IFACE="$cluster_iface" TORCH_XCCL_ASYNC_ERROR_HANDLING=1 LD_LIBRARY_PATH="$native_library_path" \
  VLLM_KV_CACHE_LAYOUT=NHD VLLM_XPU_EXACT_SPEC_ATTN=1 VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1 VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1 VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1 VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE="$se" VLLM_XPU_LAGUNA_M8_QKNORM_ROPE="$qk" VLLM_XPU_LAGUNA_M8_W1_N_TILE=64 VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK="$width12_stack" VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK="$width12_stack" VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE="$width12_stack" VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16="$dflash_fp8" VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0 VLLM_XPU_LAGUNA_PARITY_PROBE=0 VLLM_TRACE_FUNCTION=0 VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0 VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=0 VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM=0 VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=0 VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM=0 VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=0 VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE=0 VLLM_DISABLE_SHARED_EXPERTS_STREAM=0 VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD=256 VLLM_XPU_EXPERT_MAP_ROUND_ROBIN=0 VLLM_XPU_V4_M1_BIASED_TOPK=0 VLLM_XPU_V4_M1_ROUTER_NORM=0 VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0 VLLM_USE_AOT_COMPILE=0 LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS="$laguna_spec" VLLM_XPU_LAGUNA_EXACT_MAX_M="$laguna_m" VLLM_XPU_LAGUNA_DRAFT_BREAKABLE_GRAPH="$draft_graph" LAGUNA_M="$laguna_m" LAGUNA_SPEC="$laguna_spec" LAGUNA_GPU_UTIL="$gpu_util" LAGUNA_LOCAL_ARGMAX="$([[ "$local_argmax" == 1 ]] && echo true || echo false)" VLLM_XPU_LAGUNA_CAPTURE_FILTER_DEBUG=1 VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH="$graph" VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS="$capture_attention" VLLM_XPU_LAGUNA_M8_INLINE_ATTENTION_GRAPHS="$inline_attention" VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA="$metadata_arg" VLLM_USE_BREAKABLE_CUDAGRAPH="$graph" XPU_GRAPH="$graph" VLLM_XPU_ENABLE_XPU_GRAPH="$graph" \
  REPRO_MODEL_ROOT="$LAGUNA_NVME_MODEL_ROOT" REPRO_ARTIFACT_ROOT="$LAGUNA_NVME_ARTIFACT_ROOT" REPRO_NVME_DEVICE="$LAGUNA_NVME_DEVICE" REPRO_NVME_FSTYPE="$LAGUNA_NVME_FSTYPE" \
  "$serve_script" "$run_dir" >"$run_dir/server.log" 2>&1 &
server_pid="$!"; printf '%s\n' "$server_pid" > "$run_dir/server.pid"
for _ in $(seq 1 180); do curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1 && break; service_alive || die "service exited before health"; sleep 5; done
curl -fsS http://127.0.0.1:18080/health >/dev/null || die "service startup timed out"
tr '\0' '\n' < "/proc/$server_pid/environ" | LC_ALL=C sort > "$run_dir/service-environment.txt"
grep -Fx "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=$width12_stack" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=$width12_stack" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=$width12_stack" "$run_dir/service-environment.txt" >/dev/null
grep -Fx "VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=$dflash_fp8" "$run_dir/service-environment.txt" >/dev/null
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-before-suite.prom"
cd "$repo_root"
"$venv_python" "$benchmark" --base-url http://127.0.0.1:18080 --model laguna-s-2.1-int4 --suite experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json --max-tokens 512 --metric-tokens 100 --seed 1 --timeout 1800 --return-token-ids --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}' --out "$run_dir/bench.json" > "$run_dir/bench.stdout"
"$venv_python" "$metric_qualifier" "$run_dir/bench.json" --in-place > "$run_dir/metric-accounting.stdout"
curl -fsS http://127.0.0.1:18080/metrics > "$run_dir/metrics-after-suite.prom"
comparator_args=(--teacher "$teacher" --require-text-hash)
if [[ -n "$teacher_text_oracle" ]]; then
  comparator_args+=(--teacher-text-oracle "$teacher_text_oracle")
fi
"$venv_python" "$comparator" "${comparator_args[@]}" --candidate "$run_dir/bench.json" --out "$run_dir/exactness-vs-q1.json" > "$run_dir/exactness-vs-q1.stdout"
jq -e '.fresh_response_validity.valid == true and .fresh_response_validity.each_prompt_run_once == true and .fresh_response_validity.cached_tokens_all_zero == true and .realistic_final_gate.passed == true and .run_identity.prompt_count == 13 and .run_identity.max_tokens == 512 and .run_identity.seed == 1' "$run_dir/bench.json" >/dev/null
jq -e '.all_exact == true and .candidates[0].comparison.exact_count == 13 and .candidates[0].comparison.total == 13 and .candidates[0].comparison.all_cached_zero == true and .candidates[0].comparison.text_sha256_checked_count == 13 and .candidates[0].comparison.all_text_sha256_equal == true' "$run_dir/exactness-vs-q1.json" >/dev/null
"$venv_python" - "$run_dir/server.log" "$expected_num_graphs" "$expected_num_eager_breaks" "$dflash_fp8" <<'PY'
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
expected_shape = (
    f"(graphs={int(sys.argv[2])}, eager_breaks={int(sys.argv[3])})"
)
captures = [line for line in lines if "Captured audited breakable cudagraph" in line]
replays = [line for line in lines if "Replayed audited breakable cudagraph" in line]
rank = re.compile(r"Worker_TP([0-3])_EP([0-3])")
expected = {(0, 0), (1, 1), (2, 2), (3, 3)}
for name, rows in (("capture", captures), ("replay", replays)):
    observed = {tuple(map(int, match.groups())) for line in rows if (match := rank.search(line))}
    if len(rows) != 4 or observed != expected:
        raise SystemExit(f"graph {name} topology mismatch: rows={len(rows)} ranks={sorted(observed)}")
    shapes = {line.split("BreakableCUDAGraphCapture")[-1] for line in rows}
    if len(shapes) != 1:
        raise SystemExit(f"graph {name} topology differs across ranks: {shapes}")
    if any(expected_shape not in line for line in rows):
        raise SystemExit(
            f"graph {name} topology is not {expected_shape}: {sorted(shapes)}"
        )
fp8_rows = [
    line for line in lines
    if "Prepared Laguna DFlash FP8 W8A16 draft projections: count=31" in line
]
fp8_ranks = {
    tuple(map(int, match.groups()))
    for line in fp8_rows
    if (match := rank.search(line))
}
if int(sys.argv[4]) == 1:
    if len(fp8_rows) != 4 or fp8_ranks != expected:
        raise SystemExit(
            "draft FP8 projection treatment mismatch: "
            f"rows={len(fp8_rows)} ranks={sorted(fp8_ranks)}"
        )
elif fp8_rows:
    raise SystemExit(
        f"draft FP8 treatment appeared in a flag-off run: rows={len(fp8_rows)}"
    )
PY
stop_service; server_pid=""
assert_no_workers || die "workers or listener survived shutdown"
capture_idle "$run_dir/post-idle.json"
verify_idle_interval poststop
mv -- "$rpc_dir" "$run_dir/rpc-after-stop"
printf 'status=PASS\n' > "$run_dir/status.txt"
echo "Laguna formal M8 metadata crossover leg PASS: $label $treatment $run_dir"
