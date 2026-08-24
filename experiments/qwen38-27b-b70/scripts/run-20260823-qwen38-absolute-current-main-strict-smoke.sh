#!/usr/bin/env bash
set -euo pipefail

# Strict one-arm runner for the locally built literal-current-main images.
# Historical rolling-image runners remain separate because they resolve a
# registry RepoDigest and expect /workspace/vllm to be a Git checkout; neither
# assumption is true for these wheel-installed immutable images.
#
# Usage:
#   run-20260823-qwen38-absolute-current-main-strict-smoke.sh \
#     LANE MTP KV MAXLEN GPUS PORT OUT_DIR SUITE CACHE_DIR
#
# LANE: control (current vLLM + stock base kernel) or both (both current).
# CACHE_POLICY: fresh, seeded-fresh, or replay. Seeded-fresh copies only a
# validated `.best_config` decision bundle into an otherwise empty cache and
# then requires a new AOT compilation. Replay additionally requires
# EXPECTED_CACHE_MANIFEST_SHA256.
# PYTHONHASHSEED_MODE: zero (default) or unset. The unset mode requires the
# host variable to be absent and omits it from the container environment.

[[ $# -eq 9 ]] || {
  printf 'usage: %s LANE MTP KV MAXLEN GPUS PORT OUT_DIR SUITE CACHE_DIR\n' \
    "$0" >&2
  exit 2
}

lane=$1
mtp=$2
kv=$3
maxlen=$4
gpu=$5
port=$6
out=$7
suite=$8
cache_dir=$9

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
if [[ -n ${LAB_REPO_ROOT:-} ]]; then
  repo=$(realpath -e -- "$LAB_REPO_ROOT")
else
  repo=$(git -C "$script_dir" rev-parse --show-toplevel)
fi
receipt=${CURRENT_MAIN_BUILD_RECEIPT:-$repo/experiments/qwen38-27b-b70/data/2026-08-23-qwen38-absolute-current-main-build.json}
model=/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan
model_manifest=${CURRENT_MAIN_MODEL_MANIFEST:-$repo/repro/qwen38-27b-autoround-int4-b70/manifests/model.json}
model_verifier=${CURRENT_MAIN_MODEL_VERIFIER:-$repo/repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py}
bench_helper=${CURRENT_MAIN_BENCH_HELPER:-$repo/scripts/bench-openai-realistic-suite.py}
quality_helper=${CURRENT_MAIN_QUALITY_HELPER:-$repo/scripts/qwen38-text-quality-suite.py}
venv=/home/steve/.venvs/vllm-xpu
expected_suite_sha256=292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c
cache_policy=${CACHE_POLICY:?set CACHE_POLICY=fresh, seeded-fresh, or replay}
best_config_seed_dir=${BEST_CONFIG_SEED_DIR:-}
expected_best_config_seed_count=${EXPECTED_BEST_CONFIG_SEED_COUNT:-}
expected_best_config_seed_manifest_sha256=${EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256:-}
best_config_target_aot_namespace=${BEST_CONFIG_TARGET_AOT_NAMESPACE:-}
expected_cache_outer_namespace=${EXPECTED_CACHE_OUTER_NAMESPACE:-}
expected_cache_code_hash=${EXPECTED_CACHE_CODE_HASH:-}
expected_cache_compiler_hash=${EXPECTED_CACHE_COMPILER_HASH:-}
expected_cache_config_hash=${EXPECTED_CACHE_CONFIG_HASH:-}
expected_cache_env_sha256=${EXPECTED_CACHE_ENV_SHA256:-}
expected_computation_graph_sha256s=${EXPECTED_COMPUTATION_GRAPH_SHA256S:-}
max_tokens=${MAX_TOKENS:-512}
bench=${BENCH:-1}
canary=${CANARY:-1}
natural_eos=${NATURAL_EOS:-0}
return_token_ids=${RETURN_TOKEN_IDS:-1}
quality=${QUALITY:-0}
quality_require_baseline=${QUALITY_REQUIRE_BASELINE:-0}
quality_baseline_json=${QUALITY_BASELINE_JSON:-}
graph=${VLLM_XPU_GRAPH:-1}
pythonhashseed_mode=${PYTHONHASHSEED_MODE:-zero}
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}
legacy_lock_file=/tmp/b70-benchmark.lock
muse_lock_file=/run/lock/muse-glimmer-gpu-exclusive.lock
expected_gpu0_bdf=0000:23:00.0
expected_gpu0_uuid=00000000-0000-0023-0000-0000e2238086
kernel_reject_pattern='Timedout job:|Kernel-submitted job timed out|VM job timed out|device coredump|GT.*reset|reset (queued|started|done)|TLB.*timeout|GuC.*(fail|error|timeout)|CT.*(fail|error|timeout)|xe.*(device.?lost|fault|reset|hung|hang[: ]|tim(e|ed)[ -]?out)|AER:.*(error|fatal|nonfatal)|Hardware Error|aer_status|RxErr|NonFatalErr|nvme.*(timeout|reset|I/O error)|EXT4-fs error|WARNING:|BUG:|Oops:'
created_container_id=
container_id_file=
container_removal_complete=0
journal_cursor=

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

non_speed_die() {
  local reason=$*
  local reason_tmp class_tmp
  [[ -d ${out:-} ]] || die "$reason"
  reason_tmp="$out/.qualification-failure.reason.txt.tmp.$$"
  class_tmp="$out/.qualification-failure.class.tmp.$$"
  printf '%s\n' "$reason" >"$reason_tmp" ||
    die 'failed to record non-speed qualification failure reason'
  mv -f -- "$reason_tmp" "$out/qualification-failure.reason.txt" ||
    die 'failed to seal non-speed qualification failure reason'
  printf 'non-speed-qualification-gate\n' >"$class_tmp" ||
    die 'failed to record non-speed qualification failure class'
  mv -f -- "$class_tmp" "$out/qualification-failure.class" ||
    die 'failed to seal non-speed qualification failure class'
  die "$reason"
}

require_fixed_text_or_non_speed() {
  local needle=$1 source_file=$2 reason=$3 checker_rc
  if grep -Fq -- "$needle" "$source_file"; then
    return 0
  else
    checker_rc=$?
  fi
  if [[ $checker_rc -eq 1 ]]; then
    non_speed_die "$reason"
  fi
  die "$reason checker failed with rc=$checker_rc"
}

require_jq_or_non_speed() {
  local filter=$1 source_file=$2 reason=$3 checker_rc
  if jq -e "$filter" "$source_file" >/dev/null; then
    return 0
  else
    checker_rc=$?
  fi
  if [[ $checker_rc -eq 1 ]]; then
    non_speed_die "$reason"
  fi
  die "$reason checker failed with rc=$checker_rc"
}

dockerc() {
  sudo -S -p '' docker "$@" <"$sudo_pass_file"
}

capture_kernel_delta() {
  local label=$1 journal_rc rg_rc
  [[ -n $journal_cursor ]] || return 2
  if timeout --signal=TERM --kill-after=5s 30s \
      journalctl -b -k --after-cursor "$journal_cursor" --no-pager \
      -o short-iso >"$out/kernel-delta.$label.log"; then
    journal_rc=0
  else
    journal_rc=$?
  fi
  [[ $journal_rc -eq 0 ]] || return "$journal_rc"
  if rg -i "$kernel_reject_pattern" "$out/kernel-delta.$label.log" \
      >"$out/kernel-reject-events.$label.log"; then
    return 1
  else
    rg_rc=$?
  fi
  [[ $rg_rc -eq 1 ]] || return "$rg_rc"
  : >"$out/kernel-reject-events.$label.log"
}

check_render_idle() {
  local label=$1 rc
  if timeout --signal=TERM --kill-after=5s 20s sudo -S -p '' fuser \
      "${render_nodes[@]}" >"$out/render-holders.$label.stdout" \
      2>"$out/render-holders.$label.stderr" <"$sudo_pass_file"; then
    rc=0
  else
    rc=$?
  fi
  printf '%s\n' "$rc" >"$out/render-holders.$label.rc"
  [[ $rc -eq 1 && ! -s $out/render-holders.$label.stdout &&
     ! -s $out/render-holders.$label.stderr ]]
}

container_id_present() {
  local target_id=$1 matches
  matches=$(dockerc ps -aq --no-trunc --filter "id=$target_id") || return 2
  [[ -z $matches ]] && return 1
  [[ $matches == "$target_id" ]] || return 2
  return 0
}

recover_owned_container_id() {
  local candidate_id
  [[ -z $created_container_id ]] || return 0
  [[ -n $container_id_file && -f $container_id_file ]] || return 1
  candidate_id=$(<"$container_id_file")
  [[ $candidate_id =~ ^[0-9a-f]{64}$ ]] || return 2
  created_container_id=$candidate_id
}

valid_sha256_ref() {
  [[ $1 =~ ^sha256:[0-9a-f]{64}$ ]]
}

valid_sha256() {
  [[ $1 =~ ^[0-9a-f]{64}$ ]]
}

cache_manifest() {
  local destination=$1
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    find . -type f -print0 | sort -z | xargs -0 -r sha256sum
  ' bash "$cache_dir" <"$sudo_pass_file" >"$destination"
}

best_config_manifest() {
  local source_dir=$1 destination=$2
  sudo -S -p '' bash -c '
    set -euo pipefail
    cd "$1"
    find . -type f -name "*.best_config" -print0 | sort -z |
      xargs -0 -r sha256sum
  ' bash "$source_dir" <"$sudo_pass_file" >"$destination"
}

cache_jq() {
  sudo -S -p '' jq "$@" <"$sudo_pass_file"
}

cache_file_sha256() {
  sudo -S -p '' sha256sum "$1" <"$sudo_pass_file" | awk '{print $1}'
}

check_label() {
  local key=$1
  local expected=$2
  local actual
  actual=$(jq -r --arg key "$key" '.[0].Config.Labels[$key] // empty' \
    "$out/image-inspect.json")
  [[ $actual == "$expected" ]] ||
    die "image label $key mismatch: expected=$expected actual=$actual"
}

validate_inherited_lock() {
  local fd=$1
  local expected_path=$2
  local competing_fd competing_rc
  [[ $fd =~ ^[0-9]+$ ]] || die "invalid inherited lock descriptor: $fd"
  [[ -e /proc/$$/fd/$fd ]] || die "inherited lock descriptor $fd is closed"
  local actual_path
  actual_path=$(readlink -f -- "/proc/$$/fd/$fd")
  [[ $actual_path == "$(readlink -f -- "$expected_path")" ]] ||
    die "inherited lock path mismatch: $actual_path != $expected_path"
  exec {competing_fd}<>"$expected_path"
  if flock -n "$competing_fd"; then
    competing_rc=0
  else
    competing_rc=$?
  fi
  exec {competing_fd}>&-
  [[ $competing_rc -eq 1 ]] || {
    [[ $competing_rc -ne 0 ]] ||
      die "inherited descriptor was not pre-locked by its parent: $expected_path"
    die "could not verify inherited lock ownership: $expected_path"
  }
  flock -n "$fd" || die "inherited lock is not exclusively held: $expected_path"
}

[[ $lane == control || $lane == both ]] || die 'LANE must be control or both'
[[ $mtp =~ ^[0-9]+$ ]] || die 'MTP must be a nonnegative integer'
[[ $kv == f16 || $kv == fp8_e4m3 || $kv == fp8_e5m2 ]] ||
  die 'KV must be f16, fp8_e4m3, or fp8_e5m2'
[[ $maxlen =~ ^[1-9][0-9]*$ ]] || die 'MAXLEN must be a positive integer'
[[ $gpu =~ ^[0-3](,[0-3])*$ ]] || die 'GPUS must be a comma-separated subset of 0..3'
[[ $port =~ ^[1-9][0-9]*$ && $port -le 65535 ]] || die 'invalid PORT'
[[ $cache_policy == fresh || $cache_policy == seeded-fresh ||
   $cache_policy == replay ]] ||
  die 'CACHE_POLICY must be fresh, seeded-fresh, or replay'
if [[ $cache_policy == seeded-fresh ]]; then
  [[ $lane == both ]] || die 'seeded-fresh is scoped to the both-current lane'
  [[ -d $best_config_seed_dir ]] ||
    die 'seeded-fresh requires BEST_CONFIG_SEED_DIR'
  [[ $expected_best_config_seed_count =~ ^[1-9][0-9]*$ ]] ||
    die 'seeded-fresh requires a positive EXPECTED_BEST_CONFIG_SEED_COUNT'
  valid_sha256 "$expected_best_config_seed_manifest_sha256" ||
    die 'seeded-fresh requires EXPECTED_BEST_CONFIG_SEED_MANIFEST_SHA256'
  [[ $best_config_target_aot_namespace =~ ^[0-9a-f]{64}$ ]] ||
    die 'seeded-fresh requires a 64-hex BEST_CONFIG_TARGET_AOT_NAMESPACE'
  [[ $expected_cache_outer_namespace =~ ^[0-9a-f]{10}$ ]] ||
    die 'seeded-fresh requires a 10-hex EXPECTED_CACHE_OUTER_NAMESPACE'
  valid_sha256 "$expected_cache_code_hash" ||
    die 'seeded-fresh requires EXPECTED_CACHE_CODE_HASH'
  [[ $expected_cache_compiler_hash =~ ^[0-9a-f]{10}$ ]] ||
    die 'seeded-fresh requires a 10-hex EXPECTED_CACHE_COMPILER_HASH'
  [[ $expected_cache_config_hash =~ ^[0-9a-f]{10}$ ]] ||
    die 'seeded-fresh requires a 10-hex EXPECTED_CACHE_CONFIG_HASH'
  valid_sha256 "$expected_cache_env_sha256" ||
    die 'seeded-fresh requires EXPECTED_CACHE_ENV_SHA256'
  [[ -n $expected_computation_graph_sha256s ]] ||
    die 'seeded-fresh requires EXPECTED_COMPUTATION_GRAPH_SHA256S'
fi
[[ $max_tokens == 512 ]] || die 'current strict qualification requires MAX_TOKENS=512'
[[ $bench == 1 && $canary == 1 && $return_token_ids == 1 ]] ||
  die 'BENCH, CANARY, and RETURN_TOKEN_IDS must all equal 1'
[[ $natural_eos == 0 || $natural_eos == 1 ]] || die 'NATURAL_EOS must be 0 or 1'
[[ $quality == 0 || $quality == 1 ]] || die 'QUALITY must be 0 or 1'
[[ $quality_require_baseline == 0 || $quality_require_baseline == 1 ]] ||
  die 'QUALITY_REQUIRE_BASELINE must be 0 or 1'
[[ $quality_require_baseline == 0 || $quality == 1 ]] ||
  die 'QUALITY_REQUIRE_BASELINE=1 requires QUALITY=1'
[[ $graph == 1 ]] || die 'this strict promotion runner requires VLLM_XPU_GRAPH=1'
[[ $pythonhashseed_mode == zero || $pythonhashseed_mode == unset ]] ||
  die 'PYTHONHASHSEED_MODE must be zero or unset'
declare -a pythonhashseed_docker_args=()
case $pythonhashseed_mode in
  zero)
    if [[ -n ${PYTHONHASHSEED-} && ${PYTHONHASHSEED-} != 0 ]]; then
      die 'PYTHONHASHSEED_MODE=zero forbids an inherited value other than 0'
    fi
    pythonhashseed_effective=0
    pythonhashseed_docker_args=(-e PYTHONHASHSEED=0)
    ;;
  unset)
    [[ ! -v PYTHONHASHSEED ]] ||
      die 'PYTHONHASHSEED_MODE=unset requires PYTHONHASHSEED to be absent'
    pythonhashseed_effective=unset
    ;;
esac
[[ -z ${EXTRA_VLLM_ARGS:-} ]] || die 'EXTRA_VLLM_ARGS is forbidden in zero-overlay qualification'
[[ -z ${PROMPT_IDS:-} ]] || die 'strict qualification requires the complete suite'
[[ ! -v ONEAPI_DEVICE_SELECTOR ]] || die 'ONEAPI_DEVICE_SELECTOR must be unset'
[[ ! -v ZE_AFFINITY_MASK ]] || die 'inherited ZE_AFFINITY_MASK must be unset'
[[ ! -v SYCL_DEVICE_FILTER ]] || die 'inherited SYCL_DEVICE_FILTER must be unset'
[[ ! -v SYCL_DEVICE_ALLOWLIST ]] || die 'inherited SYCL_DEVICE_ALLOWLIST must be unset'
[[ ! -v UR_DEVICE_SELECTORS ]] || die 'inherited UR_DEVICE_SELECTORS must be unset'
[[ -z ${XPU_GRAPH:-} ]] || die 'inherited XPU_GRAPH must be unset'
[[ -z ${COMPILATION_CONFIG:-} ]] || die 'inherited COMPILATION_CONFIG must be unset'
[[ -z ${PYTHONPATH:-} ]] || die 'inherited PYTHONPATH must be unset'
[[ -z ${LD_PRELOAD:-} ]] || die 'inherited LD_PRELOAD must be unset'
[[ -z ${LD_LIBRARY_PATH:-} ]] || die 'inherited LD_LIBRARY_PATH must be unset'
[[ -z ${VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE:-} ]] ||
  die 'autotune isolation flags are forbidden in zero-overlay qualification'
[[ -z ${VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING:-} ]] ||
  die 'autotune isolation flags are forbidden in zero-overlay qualification'
[[ -z ${TRITON_CACHE_AUTOTUNING:-} ]] ||
  die 'autotune isolation flags are forbidden in zero-overlay qualification'

while IFS='=' read -r variable _; do
  case $variable in
    VLLM_XPU_GRAPH) ;;
    VLLM_XPU_*|VLLM_INTEL_*|VLLM_USE_*|VLLM_FORCE_*|ONEAPI_*|ZE_*|ZES_*|SYCL_*|UR_*|XPU_*|CCL_*|ONECCL_*|FI_*|TORCH_XCCL_*)
      die "inherited experiment variable is forbidden: $variable"
      ;;
  esac
done < <(env)

[[ -r $sudo_pass_file ]] || die "sudo password file is unreadable: $sudo_pass_file"
for command_name in curl docker find findmnt flock fuser git jq journalctl mv \
  pgrep realpath rg sed sha256sum ss sync tail timeout tr xpu-smi; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
timeout --signal=TERM --kill-after=5s 20s sudo -S -p '' -v \
  <"$sudo_pass_file" || die 'sudo authentication preflight failed'
[[ -f $receipt ]] || die "missing build receipt: $receipt"
[[ -f $suite ]] || die "missing suite: $suite"
[[ $(sha256sum "$suite" | awk '{print $1}') == "$expected_suite_sha256" ]] ||
  die 'strict qualification suite hash changed'
[[ -f $model_manifest ]] || die "missing model manifest: $model_manifest"
[[ -x $model_verifier ]] || die "missing model verifier: $model_verifier"
[[ -f $bench_helper ]] || die "missing benchmark helper: $bench_helper"
[[ -f $quality_helper ]] || die "missing quality helper: $quality_helper"
[[ -x $venv/bin/python ]] || die "missing validation Python: $venv/bin/python"
[[ -d $model ]] || die "missing model: $model"
[[ ! -e $out ]] || die "output already exists: $out"
lab_status=$(git -C "$repo" status --porcelain=v1 --untracked-files=all) ||
  die 'lab repository status check failed'
[[ -z $lab_status ]] ||
  die 'lab repository must be completely clean'
[[ $(git -C "$repo" branch --show-current) == main ]] || die 'lab repository must be on main'
[[ $(git -C "$repo" rev-parse HEAD) == "$(git -C "$repo" rev-parse origin/main)" ]] ||
  die 'local main must equal origin/main'
live_lab_main=$(timeout --signal=TERM --kill-after=5s 30s \
  git -C "$repo" ls-remote --exit-code origin refs/heads/main |
  awk 'NR == 1 {print $1}')
[[ $live_lab_main =~ ^[0-9a-f]{40}$ ]] || die 'could not resolve live lab origin/main'
[[ $(git -C "$repo" rev-parse HEAD) == "$live_lab_main" ]] ||
  die 'local main must equal the live lab origin/main'

IFS=',' read -r -a gpu_devices <<<"$gpu"
declare -A seen_gpu=()
for device in "${gpu_devices[@]}"; do
  [[ -z ${seen_gpu[$device]:-} ]] || die "duplicate GPU index: $device"
  seen_gpu[$device]=1
done
tp=${#gpu_devices[@]}
[[ $tp -eq 1 && $gpu == 0 ]] ||
  die 'this qualification runner is intentionally scoped to TP1 on GPU 0'
[[ $mtp == 0 ]] || die 'this zero-overlay qualification runner is intentionally MTP0-only'
alias=qwen38-absolute-current-main-$lane
name=qwen38-absolute-current-main-$lane-$port

if [[ -n ${QWEN_CURRENT_MUSE_LOCK_FD:-} ]]; then
  validate_inherited_lock "$QWEN_CURRENT_MUSE_LOCK_FD" "$muse_lock_file"
else
  exec {muse_lock_fd}<>"$muse_lock_file"
  flock -n "$muse_lock_fd" || die "Muse GPU lock is held: $muse_lock_file"
  : >"$muse_lock_file"
  printf 'qwen-current-main pid=%s runner=%s\n' "$$" "$script_path" \
    >&"$muse_lock_fd"
fi

if [[ -n ${QWEN_CURRENT_HOST_LOCK_FD:-} ]]; then
  validate_inherited_lock "$QWEN_CURRENT_HOST_LOCK_FD" "$legacy_lock_file"
else
  exec {host_lock_fd}<>"$legacy_lock_file"
  flock -n "$host_lock_fd" || die "host benchmark lock is held: $legacy_lock_file"
  : >"$legacy_lock_file"
  printf 'qwen-current-main pid=%s runner=%s\n' "$$" "$script_path" \
    >&"$host_lock_fd"
fi

gpu_lease_dir=/run/user/$(id -u)/qwen36-b70-gpu-leases
mkdir -p -- "$gpu_lease_dir"
declare -a gpu_lease_fds=()
if [[ -n ${QWEN_CURRENT_GPU_LEASE_FD:-} ]]; then
  [[ $tp -eq 1 ]] || die 'one inherited GPU lease is valid only for TP1'
  validate_inherited_lock "$QWEN_CURRENT_GPU_LEASE_FD" \
    "$gpu_lease_dir/gpu${gpu_devices[0]}.lock"
else
  for device in "${gpu_devices[@]}"; do
    lease_path=$gpu_lease_dir/gpu${device}.lock
    exec {lease_fd}>"$lease_path"
    flock -n "$lease_fd" || die "GPU $device is leased"
    gpu_lease_fds+=("$lease_fd")
  done
fi

port_lease_dir=/run/user/$(id -u)/qwen36-b70-port-leases
mkdir -p -- "$port_lease_dir"
exec {port_lease_fd}>"$port_lease_dir/port${port}.lock"
flock -n "$port_lease_fd" || die "port $port is leased"

if running_container_ids=$(dockerc ps -q); then
  :
else
  die 'Docker running-container scan failed'
fi
[[ -z $running_container_ids ]] || die 'a Docker container is already running'
if existing_container_ids=$(dockerc ps -aq --no-trunc \
    --filter "name=^/${name}$"); then
  :
else
  die 'Docker container-name scan failed'
fi
[[ -z $existing_container_ids ]] ||
  die "refusing to replace pre-existing container: $name"
if model_processes=$(pgrep -af '[E]ngineCore|[v]llm serve|[l]lama-server'); then
  die 'a model server process is already running'
else
  model_pgrep_rc=$?
fi
[[ $model_pgrep_rc -eq 1 ]] || die 'model-process scan failed'
if port_listeners=$(ss -ltnH "sport = :$port"); then
  :
else
  die "port $port listener scan failed"
fi
[[ -z $port_listeners ]] || die "port $port already has a listener"

jq -e '
  .schema == "neural-download-absolute-current-main-build-v1" and
  .state == "static-preflight-passed-for-built-images-gpu-qualification-pending" and
  .mode == "--build-all" and .overlay == "none" and
  .promotion.qualified == false
' "$receipt" >/dev/null || die 'invalid or already-promoted build receipt'

archive_dir=$(jq -r .external_archive "$receipt")
[[ -d $archive_dir ]] || die "missing external build archive: $archive_dir"
(
  cd "$archive_dir"
  sha256sum -c SHA256SUMS >/dev/null
) || die 'external build archive checksum failure'
cmp -s "$receipt" "$archive_dir/build-receipt.json" ||
  die 'tracked and archived build receipts differ'
[[ $(sha256sum "$archive_dir/build-20260823-qwen38-absolute-current-main-images.sh" |
  awk '{print $1}') == "$(jq -r .build_inputs.script_sha256 "$receipt")" ]] ||
  die 'archived build-script hash differs from the build receipt'
[[ $(sha256sum "$archive_dir/Dockerfile.absolute-current-main" | awk '{print $1}') == \
   "$(jq -r .build_inputs.dockerfile_sha256 "$receipt")" ]] ||
  die 'archived Dockerfile hash differs from the build receipt'

case $lane in
  control)
    image_key=current_vllm_stock_kernel
    expected_lane=current-vllm-stock-kernel
    expected_kernel_head=stock-from-base
    expected_kernel_tree=stock-from-base
    expected_kernel_version=0.1.13.2
    expected_kernel_wheel_sha256=stock-from-base
    expected_kernel_chunk_sha256=stock-from-base
    expected_kernel_paged_sha256=stock-from-base
    archived_static_preflight=current-vllm-stock-kernel-static-preflight.txt
    ;;
  both)
    image_key=both_current_zero_overlay
    expected_lane=both-current-zero-overlay
    expected_kernel_head=$(jq -r .kernel.head "$receipt")
    expected_kernel_tree=$(jq -r .kernel.tree "$receipt")
    expected_kernel_version=$(jq -r .kernel.package_version "$receipt")
    expected_kernel_wheel_sha256=$(jq -r .kernel.official_artifact.wheel_sha256 "$receipt")
    expected_kernel_chunk_sha256=$(jq -r .kernel.official_artifact.chunk_prefill_full_sha256 "$receipt")
    expected_kernel_paged_sha256=$(jq -r .kernel.official_artifact.paged_decode_full_sha256 "$receipt")
    archived_static_preflight=both-current-zero-overlay-static-preflight.txt
    ;;
esac
image_tag=$(jq -r --arg key "$image_key" '.images[$key].tag' "$receipt")
image_id=$(jq -r --arg key "$image_key" '.images[$key].image_id' "$receipt")
valid_sha256_ref "$image_id" || die "invalid receipt image ID: $image_id"
[[ $(jq -r --arg key "$image_key" '.images[$key].static_preflight_passed' "$receipt") == true ]] ||
  die 'receipt static preflight is not passed'

vllm_head=$(jq -r .vllm.head "$receipt")
vllm_tree=$(jq -r .vllm.tree "$receipt")
vllm_package_version=$(jq -r .vllm.package_version "$receipt")
kernel_head=$(jq -r .kernel.head "$receipt")
kernel_tree=$(jq -r .kernel.tree "$receipt")
base_digest=$(jq -r .base_digest "$receipt")
source_identity=$archive_dir/source-identity.json
[[ -f $source_identity ]] || die "missing archived source identity: $source_identity"
rust_extension_sha256=$(jq -r .reused_rust.extension_sha256 "$source_identity")
rust_frontend_sha256=$(jq -r .reused_rust.frontend_sha256 "$source_identity")
expected_static_preflight_sha256=$(jq -r --arg key "$image_key" \
  '.images[$key].static_preflight_sha256' "$receipt")
[[ -f $archive_dir/$archived_static_preflight ]] ||
  die "missing archived static preflight: $archive_dir/$archived_static_preflight"
[[ $(sha256sum "$archive_dir/$archived_static_preflight" | awk '{print $1}') == \
   "$expected_static_preflight_sha256" ]] || die 'archived static-preflight hash mismatch'
remote_vllm_pre=$(timeout --signal=TERM --kill-after=5s 30s \
  git ls-remote --exit-code https://github.com/vllm-project/vllm.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_kernel_pre=$(timeout --signal=TERM --kill-after=5s 30s \
  git ls-remote --exit-code https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_base_pre=$(timeout --signal=TERM --kill-after=5s 60s \
  sudo -S -p '' docker buildx imagetools inspect vllm/vllm-openai-xpu:nightly \
  --format '{{.Manifest.Digest}}' <"$sudo_pass_file")
[[ $remote_vllm_pre == "$vllm_head" ]] || die 'vLLM main advanced; rebuild before qualification'
[[ $remote_kernel_pre == "$kernel_head" ]] || die 'XPU-kernel main advanced; rebuild before qualification'
[[ $remote_base_pre == "$base_digest" ]] || die 'official nightly base advanced; rebuild before qualification'

out_parent=$(dirname -- "$out")
cache_parent=$(dirname -- "$cache_dir")
mkdir -p -- "$out_parent" "$cache_parent"
[[ $(findmnt -n -o FSTYPE --target "$out_parent") == ext4 ]] ||
  die 'active output must be on ext4'
[[ $(findmnt -n -o FSTYPE --target "$cache_parent") == ext4 ]] ||
  die 'active cache must be on ext4'
mkdir -- "$out"
cp -- "$suite" "$out/validation-suite.json"
cp -- "$receipt" "$out/build-receipt.json"
printf '%s\n' "$remote_vllm_pre" >"$out/upstream-vllm.pre.txt"
printf '%s\n' "$remote_kernel_pre" >"$out/upstream-kernel.pre.txt"
printf '%s\n' "$remote_base_pre" >"$out/upstream-nightly-base.pre.txt"

prelaunch_cleanup() {
  local rc=$?
  trap - EXIT
  trap '' INT TERM HUP
  [[ -f $out/final.status ]] || printf 'fail-prelaunch rc=%s\n' "$rc" >"$out/final.status"
  exit "$rc"
}
trap prelaunch_cleanup EXIT

dockerc image inspect "$image_tag" >"$out/image-tag-inspect.json" ||
  die "local image tag is absent: $image_tag"
tag_id=$(dockerc image inspect "$image_tag" --format '{{.Id}}')
[[ $tag_id == "$image_id" ]] || die "image tag moved: $tag_id != $image_id"
dockerc image inspect "$image_id" >"$out/image-inspect.json"
[[ $(jq -r '.[0].Id' "$out/image-inspect.json") == "$image_id" ]] ||
  die 'immutable image inspection returned the wrong ID'
jq -e '
  .[0].Config.Entrypoint == ["vllm", "serve"] and
  ([.[0].Config.Env[] |
    select(test("^(ONEAPI_DEVICE_SELECTOR|ZE_AFFINITY_MASK|SYCL_DEVICE_FILTER|SYCL_DEVICE_ALLOWLIST|UR_DEVICE_SELECTORS)="))] |
  length == 0)
' "$out/image-inspect.json" >/dev/null ||
  die 'immutable image bakes a device selector or affinity mask'
check_label neural.download.base.digest "$base_digest"
check_label neural.download.build.lane "$expected_lane"
check_label neural.download.overlay none
check_label neural.download.vllm.head "$vllm_head"
check_label neural.download.vllm.tree "$vllm_tree"
check_label neural.download.kernel.head "$expected_kernel_head"
check_label neural.download.kernel.tree "$expected_kernel_tree"
check_label neural.download.kernel.wheel.sha256 "$expected_kernel_wheel_sha256"
check_label neural.download.kernel.chunk_config.sha256 "$expected_kernel_chunk_sha256"
check_label neural.download.kernel.paged_config.sha256 "$expected_kernel_paged_sha256"
check_label neural.download.lab.head "$(jq -r .lab.head "$receipt")"
check_label neural.download.lab.tree "$(jq -r .lab.tree "$receipt")"
check_label neural.download.build.script.sha256 "$(jq -r .build_inputs.script_sha256 "$receipt")"
check_label neural.download.build.dockerfile.sha256 "$(jq -r .build_inputs.dockerfile_sha256 "$receipt")"
check_label neural.download.rust.extension.sha256 "$rust_extension_sha256"
check_label neural.download.rust.frontend.sha256 "$rust_frontend_sha256"
check_label neural.download.vllm.archive.sha256 "$(jq -r .vllm.source_archive_sha256 "$receipt")"
check_label neural.download.vllm.wheel.sha256 "$(jq -r .vllm.wheel_sha256 "$receipt")"
check_label org.opencontainers.image.revision "$vllm_head"

dockerc run --rm --network=none --entrypoint /bin/bash "$image_id" -lc \
  'set -euo pipefail
  if test -e /workspace/vllm || test -L /workspace/vllm; then
    test -d /workspace/vllm
    test ! -L /workspace/vllm
    test -z "$(find /workspace/vllm -mindepth 1 -print -quit)"
  fi
  cat /opt/neural-download/source-identity.json' \
  >"$out/in-image-source-identity.json"
dockerc run --rm --network=none --entrypoint /bin/bash "$image_id" -lc \
  'cat /opt/neural-download/import-receipt.json' >"$out/in-image-import-receipt.json"
dockerc run --rm --network=none --entrypoint /bin/bash "$image_id" -lc \
  'cat /opt/neural-download/pip-check.txt' >"$out/in-image-pip-check.txt"
cmp -s "$source_identity" "$out/in-image-source-identity.json" ||
  die 'in-image and archived source identities differ'
jq -e --arg head "$vllm_head" --arg tree "$vllm_tree" '
  .overlay == "none" and .vllm.head == $head and .vllm.tree == $tree
' "$out/in-image-source-identity.json" >/dev/null || die 'in-image source identity mismatch'
jq -e \
  --arg lane "$expected_lane" \
  --arg head "$vllm_head" \
  --arg version "$vllm_package_version" \
  --arg kernel_head "$expected_kernel_head" \
  --arg kernel_version "$expected_kernel_version" \
  --arg rust_extension "$rust_extension_sha256" \
  --arg rust_frontend "$rust_frontend_sha256" '
  .build_lane == $lane and .vllm_head == $head and .vllm_version == $version and
  .kernel_head == $kernel_head and .kernel_version == $kernel_version and
  .rust_extension_sha256 == $rust_extension and
  .rust_frontend_sha256 == $rust_frontend and
  (.vllm_file | startswith("/opt/venv/lib/python3.12/site-packages/vllm/"))
' "$out/in-image-import-receipt.json" >/dev/null || die 'in-image import receipt mismatch'
expected_pip_issues=1
[[ $lane == both ]] && expected_pip_issues=2
[[ $(grep -c '^The package ' "$out/in-image-pip-check.txt") -eq $expected_pip_issues ]] ||
  die 'unexpected pip-check issue count'
grep -Fx 'The package `nixl` requires `nixl-cu13==1.3.2`, but it'"'"'s not installed' \
  "$out/in-image-pip-check.txt" >/dev/null || die 'known NIXL diagnostic changed'
if [[ $lane == both ]]; then
  grep -Fx "The package \`vllm\` requires \`vllm-xpu-kernels==0.1.13.2\`, but \`$expected_kernel_version\` is installed" \
    "$out/in-image-pip-check.txt" >/dev/null || die 'exact current-kernel metadata diagnostic changed'
fi

if "$model_verifier" "$model_manifest" "$model" \
    --json "$out/model-direct-and-ordinary-verify.json" \
    >"$out/model-direct-and-ordinary-verify.log" 2>&1; then
  model_verifier_rc=0
else
  model_verifier_rc=$?
fi
if [[ $model_verifier_rc -eq 1 ]] &&
    jq -e '.status == "mismatch" and (.files | length) == 19 and
      any(.files[]; .ok != true) and
      all(.files[]; ((.error? // "") | startswith("ordinary read failed:") | not))' \
      "$out/model-direct-and-ordinary-verify.json" >/dev/null 2>&1; then
  non_speed_die 'model direct-and-ordinary identity mismatch'
fi
[[ $model_verifier_rc -eq 0 ]] ||
  die "model direct-and-ordinary identity verification was incomplete rc=$model_verifier_rc"
jq -e '.status == "verified" and (.files | length) == 19 and all(.files[]; .ok == true)' \
  "$out/model-direct-and-ordinary-verify.json" >/dev/null ||
  die 'model verifier success artifact did not certify all 19 files'
sha256sum "$model_manifest" "$suite" \
  "$bench_helper" "$quality_helper" "$model_verifier" "$script_path" \
  >"$out/input-files.sha256"
uname -a >"$out/host-uname.txt"
ls -l /dev/dri/by-path >"$out/host-dri-by-path.txt"

discovery_json=$(env -u ONEAPI_DEVICE_SELECTOR -u ZE_AFFINITY_MASK \
  -u SYCL_DEVICE_FILTER -u SYCL_DEVICE_ALLOWLIST -u UR_DEVICE_SELECTORS \
  xpu-smi discovery -j 2>/dev/null) || die 'xpu-smi discovery failed'
printf '%s\n' "$discovery_json" >"$out/xpu-smi-discovery.json"
jq -e --arg bdf "$expected_gpu0_bdf" --arg uuid "$expected_gpu0_uuid" '
  ([.device_list[] | select(.device_name | contains("Arc(TM) Pro B70"))] | length) == 4 and
  ([.device_list[] | select(.device_id == 0)] | length) == 1 and
  any(.device_list[];
    .device_id == 0 and .pci_bdf_address == $bdf and .uuid == $uuid)
' "$out/xpu-smi-discovery.json" >/dev/null || die 'GPU0 BDF/UUID identity changed'
mapfile -t render_nodes < <(find /dev/dri -maxdepth 1 -type c -name 'renderD*' -print | sort)
[[ ${#render_nodes[@]} -eq 4 ]] || die 'expected exactly four render nodes'
check_render_idle pre || die 'render-node occupancy scan failed or found a holder'
gpu0_render_node=$(realpath -e -- "/dev/dri/by-path/pci-$expected_gpu0_bdf-render")
[[ $gpu0_render_node == /dev/dri/renderD* ]] || die 'GPU0 render-node mapping changed'
printf 'ordinal=0\nbdf=%s\nuuid=%s\nrender_node=%s\n' \
  "$expected_gpu0_bdf" "$expected_gpu0_uuid" "$gpu0_render_node" \
  >"$out/gpu0-device-identity.env"

best_config_seed_target=
if [[ $cache_policy == fresh || $cache_policy == seeded-fresh ]]; then
  [[ ! -e $cache_dir ]] || die "fresh cache already exists: $cache_dir"
  mkdir -- "$cache_dir"
else
  [[ -d $cache_dir ]] || die "replay cache is missing: $cache_dir"
  valid_sha256 "${EXPECTED_CACHE_MANIFEST_SHA256:-}" ||
    die 'replay requires EXPECTED_CACHE_MANIFEST_SHA256'
  cache_manifest "$out/cache-manifest.pre.sha256"
  [[ $(sha256sum "$out/cache-manifest.pre.sha256" | awk '{print $1}') == \
     "$EXPECTED_CACHE_MANIFEST_SHA256" ]] || die 'replay cache manifest mismatch'
fi

if [[ $cache_policy == seeded-fresh ]]; then
  seed_real=$(realpath -e -- "$best_config_seed_dir")
  cache_real=$(realpath -m -- "$cache_dir")
  out_real=$(realpath -m -- "$out")
  if [[ $seed_real == "$cache_real" || $seed_real == "$cache_real"/* ||
        $cache_real == "$seed_real"/* ]]; then
    die 'seed and cache paths must be disjoint'
  fi
  if [[ $seed_real == "$out_real" || $seed_real == "$out_real"/* ||
        $out_real == "$seed_real"/* ]]; then
    die 'seed and output paths must be disjoint'
  fi
  [[ ! -L $best_config_seed_dir ]] || die 'seed directory must not be a symlink'
  [[ -z $(find "$best_config_seed_dir" -type l -print -quit) ]] ||
    die 'seed directory contains a symlink'
  seed_total_files=$(find "$best_config_seed_dir" -type f | wc -l)
  seed_best_config_files=$(find "$best_config_seed_dir" -type f \
    -name '*.best_config' | wc -l)
  [[ $seed_total_files == "$expected_best_config_seed_count" ]] ||
    die "seed bundle has unexpected total file count: $seed_total_files"
  [[ $seed_best_config_files == "$expected_best_config_seed_count" ]] ||
    die "seed bundle has unexpected .best_config count: $seed_best_config_files"
  invalid_seed_path=$(find "$best_config_seed_dir" -type f -printf '%P\n' |
    grep -Ev '^[0-9a-z]{2}/[0-9a-f]{64}\.best_config$' | head -n 1 || true)
  [[ -z $invalid_seed_path ]] || die "invalid seed relative path: $invalid_seed_path"
  while IFS= read -r -d '' seed_file; do
    jq -e '
      type == "object" and
      (.configs_hash | type == "string" and test("^[0-9a-f]{64}$")) and
      (.triton_cache_hash | type == "string" and length > 0) and
      (.num_warps | type == "number") and
      (.num_stages | type == "number")
    ' "$seed_file" >/dev/null || die "invalid best-config JSON: $seed_file"
  done < <(find "$best_config_seed_dir" -type f -name '*.best_config' \
    -print0 | sort -z)
  best_config_manifest "$best_config_seed_dir" \
    "$out/best-config-seed.source.sha256"
  actual_seed_manifest_sha=$(sha256sum "$out/best-config-seed.source.sha256" |
    awk '{print $1}')
  [[ $actual_seed_manifest_sha == "$expected_best_config_seed_manifest_sha256" ]] ||
    die "seed bundle manifest mismatch: $actual_seed_manifest_sha"

  best_config_seed_target="$cache_dir/vllm/torch_compile_cache/torch_aot_compile/$best_config_target_aot_namespace/inductor_cache"
  mkdir -p -- "$best_config_seed_target"
  while IFS= read -r -d '' seed_file; do
    relative_seed_file=${seed_file#"$best_config_seed_dir"/}
    mkdir -p -- "$best_config_seed_target/$(dirname -- "$relative_seed_file")"
    cp --reflink=never -- "$seed_file" \
      "$best_config_seed_target/$relative_seed_file"
  done < <(find "$best_config_seed_dir" -type f -name '*.best_config' \
    -print0 | sort -z)
  best_config_manifest "$best_config_seed_target" \
    "$out/best-config-seed.precompile.sha256"
  cmp -s "$out/best-config-seed.source.sha256" \
    "$out/best-config-seed.precompile.sha256" ||
    die 'seed target differs before compilation'
  preseed_total_files=$(find "$cache_dir" -type f | wc -l)
  [[ $preseed_total_files == "$expected_best_config_seed_count" ]] ||
    die "seeded fresh cache contains unexpected precompile artifacts: $preseed_total_files"
fi

compilation_config='{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2}'
args=(
  "$model" --host 0.0.0.0 --port 8000 --trust-remote-code
  --served-model-name "$alias" --tensor-parallel-size "$tp"
  --pipeline-parallel-size 1 --data-parallel-size 1
  --max-model-len "$maxlen" --max-num-seqs 1 --max-num-batched-tokens 1024
  --gpu-memory-utilization 0.90 --dtype float16 --reasoning-parser qwen3
  --default-chat-template-kwargs '{"enable_thinking": false}'
  --enable-prompt-tokens-details --no-enable-prefix-caching
  --enable-chunked-prefill --async-scheduling
  --compilation-config "$compilation_config"
)
[[ $kv != f16 ]] && args+=(--kv-cache-dtype "$kv")
[[ $mtp != 0 ]] && args+=(
  --speculative-config "{\"method\":\"qwen3_next_mtp\",\"num_speculative_tokens\":$mtp}"
)
printf '%s\n' "${args[@]}" >"$out/server-args.txt"

{
  printf 'lane=%s\nimage_tag=%s\nimage_id=%s\n' "$lane" "$image_tag" "$image_id"
  printf 'vllm_head=%s\ncomparison_kernel_head=%s\n' "$vllm_head" "$kernel_head"
  printf 'effective_kernel_head=%s\neffective_kernel_tree=%s\n' \
    "$expected_kernel_head" "$expected_kernel_tree"
  printf 'effective_kernel_version=%s\n' "$expected_kernel_version"
  printf 'tp=%s\ngpus=%s\nmtp=%s\nkv=%s\nmax_model_len=%s\n' \
    "$tp" "$gpu" "$mtp" "$kv" "$maxlen"
  printf 'cache_policy=%s\ncache_dir=%s\n' "$cache_policy" "$cache_dir"
  if [[ $cache_policy == seeded-fresh ]]; then
    printf 'best_config_seed_dir=%s\n' "$best_config_seed_dir"
    printf 'best_config_seed_count=%s\n' "$expected_best_config_seed_count"
    printf 'best_config_seed_manifest_sha256=%s\n' \
      "$expected_best_config_seed_manifest_sha256"
    printf 'best_config_target_aot_namespace=%s\n' \
      "$best_config_target_aot_namespace"
    printf 'source_overlay=none\ndecision_overlay=best_config_only\n'
  else
    printf 'source_overlay=none\ndecision_overlay=none\n'
  fi
  printf 'max_tokens=%s\nbench=%s\ncanary=%s\nnatural_eos=%s\n' \
    "$max_tokens" "$bench" "$canary" "$natural_eos"
  printf 'return_token_ids=%s\nquality=%s\nquality_require_baseline=%s\n' \
    "$return_token_ids" "$quality" "$quality_require_baseline"
  printf 'quality_baseline_json=%s\n' "${quality_baseline_json:-unset}"
  if [[ -n $quality_baseline_json ]]; then
    printf 'quality_baseline_sha256=%s\n' \
      "$(sha256sum "$quality_baseline_json" | awk '{print $1}')"
  fi
  printf 'vllm_xpu_enable_xpu_graph=%s\n' "$graph"
  printf 'pythonhashseed=%s\n' "$pythonhashseed_effective"
  printf 'pythonhashseed_mode=%s\npythonhashseed_effective=%s\n' \
    "$pythonhashseed_mode" "$pythonhashseed_effective"
  printf 'compilation_config=%s\nasync_scheduling=true\n' "$compilation_config"
  printf 'gpu_memory_utilization=0.90\nmax_num_seqs=1\nmax_num_batched_tokens=1024\n'
  printf 'prefix_caching=false\nchunked_prefill=true\n'
  printf 'lab_git_head=%s\n' "$(git -C "$repo" rev-parse HEAD)"
} >"$out/identity.env"

remove_owned_container() {
  local observed_image observed_name state evidence_failed=0 removal_failed=0
  [[ $container_removal_complete == 0 ]] || return 0
  dockerc version >/dev/null 2>&1 || return 1
  if recover_owned_container_id; then
    :
  else
    state=$?
    [[ $state -eq 1 ]] && return 0
    return 1
  fi
  if container_id_present "$created_container_id"; then
    :
  else
    state=$?
    if [[ $state -eq 1 ]]; then
      created_container_id=
    fi
    return 1
  fi
  observed_name=$(dockerc container inspect "$created_container_id" \
    --format '{{.Name}}' 2>/dev/null) || evidence_failed=1
  [[ $observed_name == "/$name" ]] || evidence_failed=1
  observed_image=$(dockerc container inspect "$created_container_id" \
    --format '{{.Image}}' 2>/dev/null) || evidence_failed=1
  [[ -z $observed_image || $observed_image == "$image_id" ]] || return 1
  dockerc logs "$created_container_id" >"$out/server.log" 2>&1 || evidence_failed=1
  dockerc inspect "$created_container_id" >"$out/container-inspect.json" 2>/dev/null ||
    evidence_failed=1
  dockerc rm -f "$created_container_id" >/dev/null 2>&1 || removal_failed=1
  if container_id_present "$created_container_id"; then
    removal_failed=1
  else
    state=$?
    [[ $state -eq 1 ]] || removal_failed=1
  fi
  [[ $removal_failed == 0 ]] || return 1
  created_container_id=
  container_removal_complete=1
  [[ $evidence_failed == 0 ]]
}

cleanup() {
  local rc=$?
  local cleanup_failed=0 cleanup_cmp_rc
  local cleanup_manifest_sha256
  trap - EXIT
  trap '' INT TERM HUP
  remove_owned_container || cleanup_failed=1
  if [[ -n $journal_cursor ]]; then
    capture_kernel_delta cleanup || cleanup_failed=1
    kernel_taint_cleanup=$(</proc/sys/kernel/tainted)
    printf '%s\n' "$kernel_taint_cleanup" >"$out/kernel-taint.cleanup.txt" ||
      cleanup_failed=1
    [[ $kernel_taint_cleanup == 0 ]] || cleanup_failed=1
    check_render_idle cleanup || cleanup_failed=1
  fi
  if [[ -d $cache_dir ]]; then
    cache_manifest "$out/cache-manifest.post.sha256" || cleanup_failed=1
    if [[ -f $out/cache-manifest.post.sha256 ]]; then
      cleanup_manifest_sha256=$(sha256sum "$out/cache-manifest.post.sha256" |
        awk '{print $1}') || cleanup_failed=1
      if [[ $cleanup_failed == 0 ]]; then
        printf '%s\n' "$cleanup_manifest_sha256" \
          >"$out/cache-manifest.post.sha256.digest" || cleanup_failed=1
      fi
      if [[ $cache_policy == replay && -f $out/cache-manifest.pre.sha256 ]]; then
        if cmp -s "$out/cache-manifest.pre.sha256" \
            "$out/cache-manifest.post.sha256"; then
          :
        else
          cleanup_cmp_rc=$?
          if [[ $cleanup_cmp_rc -eq 1 &&
                -f $out/qualification-failure.class &&
                -f $out/qualification-failure.reason.txt &&
                $(<"$out/qualification-failure.class") == \
                  non-speed-qualification-gate &&
                $(<"$out/qualification-failure.reason.txt") == \
                  'replay mutated the sealed compilation cache' ]]; then
            :
          else
            cleanup_failed=1
          fi
        fi
      fi
    fi
  fi
  if [[ $cleanup_failed == 1 ]]; then
    printf 'fail-cleanup body_rc=%s\n' "$rc" >"$out/final.status"
    exit 7
  fi
  if [[ $rc -ne 0 && -f $out/final.status &&
        $(<"$out/final.status") == pass ]]; then
    printf 'fail-after-pass body_rc=%s\n' "$rc" >"$out/final.status"
  fi
  if [[ ! -f $out/final.status ]]; then
    [[ $rc -ne 0 ]] || rc=1
    printf 'fail rc=%s\n' "$rc" >"$out/final.status"
  fi
  sync "$out" || {
    printf 'fail-sync body_rc=%s\n' "$rc" >"$out/final.status"
    exit 8
  }
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

kernel_taint_pre=$(</proc/sys/kernel/tainted)
printf '%s\n' "$kernel_taint_pre" >"$out/kernel-taint.pre.txt"
[[ $kernel_taint_pre == 0 ]] || die 'kernel is tainted before model launch'
timeout --signal=TERM --kill-after=5s 30s \
  journalctl -b -k -n 1 --show-cursor --no-pager -o short-iso \
  >"$out/kernel-baseline.log"
journal_cursor=$(sed -n 's/^-- cursor: //p' "$out/kernel-baseline.log" | tail -1)
[[ -n $journal_cursor ]] || die 'failed to capture prelaunch kernel cursor'

container_id_file=$out/container-id.txt
[[ ! -e $container_id_file ]] || die "container ID file already exists: $container_id_file"
dockerc run -d --cidfile "$container_id_file" --name "$name" \
  --device /dev/dri --group-add 44 --group-add 992 --ipc=host \
  -v /dev/dri/by-path:/dev/dri/by-path:ro \
  -v "$model:$model:ro" \
  -v "$cache_dir:/run-cache" \
  -p "127.0.0.1:$port:8000" \
  -e CCL_ZE_IPC_EXCHANGE=sockets \
  -e ZE_AFFINITY_MASK="$gpu" \
  -e VLLM_NO_USAGE_STATS=1 \
  -e VLLM_CACHE_ROOT=/run-cache/vllm \
  -e XDG_CACHE_HOME=/run-cache/xdg \
  -e VLLM_XPU_ENABLE_XPU_GRAPH=1 \
  "${pythonhashseed_docker_args[@]}" \
  --shm-size 16g "$image_id" "${args[@]}" >"$out/docker-run.stdout"
[[ -f $container_id_file ]] || die 'Docker did not write the required container ID file'
created_container_id=$(<"$container_id_file")
[[ $created_container_id =~ ^[0-9a-f]{64}$ ]] || die 'Docker returned an invalid container ID'
[[ $(tr -d '\n' <"$out/docker-run.stdout") == "$created_container_id" ]] ||
  die 'Docker stdout and CID-file container IDs differ'
[[ $(dockerc container inspect "$name" --format '{{.Id}}') == "$created_container_id" ]] ||
  die 'container name does not resolve to the invocation-owned ID'
container_image_id=$(dockerc inspect "$created_container_id" --format '{{.Image}}')
[[ $container_image_id == "$image_id" ]] || die 'container launched the wrong image ID'
printf '%s\n' "$container_image_id" >"$out/container-image-id.txt"
dockerc inspect "$created_container_id" >"$out/container-inspect.running.json"
dockerc exec "$created_container_id" /usr/bin/env | sort >"$out/container-environment.txt"
dockerc exec "$created_container_id" /bin/bash -c \
  "tr '\\0' '\\n' </proc/1/environ | sort" \
  >"$out/container-init-environment.txt"
for environment_evidence in container-environment.txt \
    container-init-environment.txt; do
  for expected_env in \
    CCL_ZE_IPC_EXCHANGE=sockets \
    VLLM_CACHE_ROOT=/run-cache/vllm \
    VLLM_NO_USAGE_STATS=1 \
    VLLM_XPU_ENABLE_XPU_GRAPH=1 \
    XDG_CACHE_HOME=/run-cache/xdg \
    ZE_AFFINITY_MASK=0; do
    grep -Fx "$expected_env" "$out/$environment_evidence" >/dev/null ||
      die "required container environment is absent from $environment_evidence: $expected_env"
  done
done
case $pythonhashseed_mode in
  zero)
    jq -e '
      [.[0].Config.Env[] | select(startswith("PYTHONHASHSEED="))] ==
      ["PYTHONHASHSEED=0"]
    ' "$out/container-inspect.running.json" >/dev/null ||
      die 'PYTHONHASHSEED_MODE=zero is wrong in Docker Config.Env'
    for environment_evidence in container-environment.txt \
      container-init-environment.txt; do
      grep -Fx 'PYTHONHASHSEED=0' "$out/$environment_evidence" >/dev/null ||
        die "PYTHONHASHSEED_MODE=zero is absent from $environment_evidence"
    done
    container_pythonhashseed_present=true
    container_pythonhashseed_effective=0
    ;;
  unset)
    jq -e '
      [.[0].Config.Env[] | select(startswith("PYTHONHASHSEED="))] | length == 0
    ' "$out/container-inspect.running.json" >/dev/null ||
      die 'PYTHONHASHSEED_MODE=unset leaked into Docker Config.Env'
    for environment_evidence in container-environment.txt \
      container-init-environment.txt; do
      if grep -q '^PYTHONHASHSEED=' "$out/$environment_evidence"; then
        die "PYTHONHASHSEED_MODE=unset leaked into $environment_evidence"
      fi
    done
    container_pythonhashseed_present=false
    container_pythonhashseed_effective=unset
    ;;
esac
printf 'requested_mode=%s\ncontainer_variable_present=%s\ncontainer_effective=%s\n' \
  "$pythonhashseed_mode" "$container_pythonhashseed_present" \
  "$container_pythonhashseed_effective" >"$out/pythonhashseed-mode.env"
for environment_evidence in container-environment.txt \
    container-init-environment.txt; do
  awk -F= '
    {reject=0}
    $1 ~ /^VLLM_XPU_/ && $1 != "VLLM_XPU_ENABLE_XPU_GRAPH" {reject=1}
    $1 ~ /^(VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE|VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING|TRITON_CACHE_AUTOTUNING)$/ {reject=1}
    $1 ~ /^(ONEAPI_DEVICE_SELECTOR|SYCL_DEVICE_FILTER|SYCL_DEVICE_ALLOWLIST|UR_DEVICE_SELECTORS|XPU_GRAPH|COMPILATION_CONFIG|PYTHONPATH|LD_PRELOAD)$/ {reject=1}
    $1 ~ /^(CCL_|ONECCL_)/ && $1 != "CCL_ZE_IPC_EXCHANGE" {reject=1}
    reject {print > "/dev/stderr"; bad=1}
    END {exit bad ? 1 : 0}
  ' "$out/$environment_evidence" ||
    die "forbidden experiment environment reached $environment_evidence"
done

healthy=0
for _ in $(seq 1 240); do
  if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  [[ $(dockerc inspect "$name" --format '{{.State.Running}}' 2>/dev/null || echo false) == true ]] ||
    die 'server container exited during startup'
  sleep 5
done
[[ $healthy == 1 ]] || die 'server did not become healthy within 20 minutes'
dockerc exec "$name" /opt/venv/bin/python -c '
import importlib.metadata as m
import pathlib
import vllm
legacy_source_dir = pathlib.Path("/workspace/vllm")
assert not legacy_source_dir.is_symlink()
assert not legacy_source_dir.exists() or (
    legacy_source_dir.is_dir() and not any(legacy_source_dir.iterdir())
)
assert pathlib.Path(vllm.__file__).resolve().is_relative_to(pathlib.Path("/opt/venv/lib/python3.12/site-packages"))
print("vllm", vllm.__version__)
print("vllm-xpu-kernels", m.version("vllm-xpu-kernels"))
' >"$out/stack-versions.txt" 2>&1
dockerc logs "$name" >"$out/server-startup.log" 2>&1
grep -m1 -F 'non-default args:' "$out/server-startup.log" \
  >"$out/effective-cli-config.txt" || die 'effective CLI config is absent'
grep -m1 -F 'Initializing a V1 LLM engine' "$out/server-startup.log" \
  >"$out/effective-engine-config.txt" || die 'effective engine config is absent'
for cli_field in \
  "'gpu_memory_utilization': 0.9" \
  "'max_num_batched_tokens': 1024" \
  "'max_num_seqs': 1" \
  "'async_scheduling': True"; do
  require_fixed_text_or_non_speed "$cli_field" \
    "$out/effective-cli-config.txt" \
    "effective CLI config is missing: $cli_field"
done
for engine_field in \
  "model='$model'" \
  'speculative_config=None' \
  'dtype=torch.float16' \
  'max_seq_len=32768' \
  'tensor_parallel_size=1' \
  'pipeline_parallel_size=1' \
  'data_parallel_size=1' \
  'decode_context_parallel_size=1' \
  'quantization=inc' \
  'enforce_eager=False' \
  'kv_cache_dtype=auto' \
  'device_config=xpu' \
  'seed=0' \
  "served_model_name=$alias" \
  'enable_prefix_caching=False' \
  'enable_chunked_prefill=True' \
  "'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE" \
  "'cudagraph_capture_sizes': [1, 2]" \
  "'max_cudagraph_capture_size': 2"; do
  require_fixed_text_or_non_speed "$engine_field" \
    "$out/effective-engine-config.txt" \
    "effective engine config is missing: $engine_field"
done
require_fixed_text_or_non_speed \
  'Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)' \
  "$out/server-startup.log" 'PIECEWISE graph capture marker is absent'
require_fixed_text_or_non_speed 'Capturing CUDA graphs (decode, FULL)' \
  "$out/server-startup.log" 'FULL graph capture marker is absent'
require_fixed_text_or_non_speed 'Graph capturing finished' \
  "$out/server-startup.log" 'graph capture completion marker is absent'

if [[ $cache_policy == seeded-fresh ]]; then
  grep -Fq 'Compiling a graph for compile range' "$out/server-startup.log" ||
    die 'seeded-fresh did not perform a fresh graph compilation'
  grep -Fq 'saved AOT compiled function' "$out/server-startup.log" ||
    die 'seeded-fresh did not save a fresh AOT compilation'
  grep -Fq "/torch_aot_compile/$best_config_target_aot_namespace/" \
    "$out/server-startup.log" ||
    die 'seeded-fresh compiled into an unexpected AOT namespace'
  if grep -Fq 'Directly load AOT compilation' "$out/server-startup.log"; then
    die 'seeded-fresh unexpectedly loaded an existing AOT model'
  fi

  IFS=',' read -r -a expected_graph_hashes <<< \
    "$expected_computation_graph_sha256s"
  [[ ${#expected_graph_hashes[@]} -eq $tp ]] ||
    die 'expected graph hash count does not match TP size'
  for rank in $(seq 0 $((tp - 1))); do
    factors="$cache_dir/vllm/torch_compile_cache/$expected_cache_outer_namespace/rank_${rank}_0/backbone/cache_key_factors.json"
    computation_graph="$cache_dir/vllm/torch_compile_cache/$expected_cache_outer_namespace/rank_${rank}_0/backbone/computation_graph.py"
    [[ -f $factors && -f $computation_graph ]] ||
      die "missing rank-$rank cache identity files"
    [[ $(cache_jq -r '.code_hash' "$factors") == "$expected_cache_code_hash" ]] ||
      die "rank-$rank code hash mismatch"
    [[ $(cache_jq -r '.compiler_hash' "$factors") == \
       "$expected_cache_compiler_hash" ]] ||
      die "rank-$rank compiler hash mismatch"
    [[ $(cache_jq -r '.config_hash' "$factors") == \
       "$expected_cache_config_hash" ]] ||
      die "rank-$rank config hash mismatch"
    actual_env_sha=$(cache_jq -S '.env' "$factors" | sha256sum |
      awk '{print $1}')
    [[ $actual_env_sha == "$expected_cache_env_sha256" ]] ||
      die "rank-$rank cache environment hash mismatch"
    [[ $(cache_file_sha256 "$computation_graph") == \
       "${expected_graph_hashes[$rank]}" ]] ||
      die "rank-$rank computation graph hash mismatch"
  done

  best_config_manifest "$best_config_seed_target" \
    "$out/best-config-seed.postcompile.sha256"
  cmp -s "$out/best-config-seed.source.sha256" \
    "$out/best-config-seed.postcompile.sha256" ||
    die 'compiler changed the seeded .best_config bundle'
  postcompile_best_config_count=$(sudo -S -p '' find "$cache_dir" -type f \
    -name '*.best_config' <"$sudo_pass_file" | wc -l)
  [[ $postcompile_best_config_count == "$expected_best_config_seed_count" ]] ||
    die "compiler added unexpected .best_config records: $postcompile_best_config_count"
fi

if "$venv/bin/python" - "http://127.0.0.1:$port" "$alias" \
    "$out/canary.json" <<'PY'
import json
import sys
import urllib.request

base_url, model, destination = sys.argv[1:]
payload = {
    "model": model,
    "messages": [{
        "role": "user",
        "content": "What does this Python expression evaluate to? Answer only the integer: sum(i * i for i in range(4))",
    }],
    "max_tokens": 8,
    "temperature": 0,
    "top_p": 1,
    "seed": 20260609,
    "chat_template_kwargs": {"enable_thinking": False},
}
request = urllib.request.Request(
    f"{base_url}/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=900) as response:
    data = json.loads(response.read())
content = (data["choices"][0]["message"].get("content") or "").strip()
cached = ((data.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens")
result = {"content": content, "cached_tokens": cached, "response": data}
with open(destination, "w") as handle:
    json.dump(result, handle, indent=2)
    handle.write("\n")
if content != "14" or cached != 0:
    raise SystemExit(3)
PY
then
  canary_rc=0
else
  canary_rc=$?
fi
if [[ $canary_rc -eq 3 ]] &&
    jq -e '(.response | type) == "object" and
      (.content != "14" or .cached_tokens != 0)' \
      "$out/canary.json" >/dev/null 2>&1; then
  non_speed_die 'arithmetic canary or cached-token-zero gate failed'
fi
[[ $canary_rc -eq 0 ]] || die "arithmetic canary was incomplete rc=$canary_rc"
printf 'canary_rc=0\n' >"$out/canary.status"
capture_kernel_delta post-canary ||
  die 'kernel rejected model startup or canary before timing'
[[ $(</proc/sys/kernel/tainted) == 0 ]] ||
  die 'kernel became tainted during model startup or canary'

curl -fsS "http://127.0.0.1:$port/metrics" >"$out/metrics.before.prom"
bench_args=(
  --base-url "http://127.0.0.1:$port" --model "$alias" --api-mode chat
  --suite "$suite" --max-tokens "$max_tokens" --metric-tokens 100
  --seed 1 --timeout 900 --out "$out/bench.json" --return-token-ids
)
if [[ $natural_eos == 1 ]]; then
  bench_args+=(--require-natural-eos
    --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false}}')
else
  bench_args+=(
    --request-extra-json '{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}')
fi
if "$venv/bin/python" "$bench_helper" \
    "${bench_args[@]}" >"$out/bench.stdout.log" 2>&1; then
  bench_rc=0
else
  bench_rc=$?
fi
prompt_count=$(jq '.prompts | length' "$suite")
if [[ $bench_rc -eq 2 ]] && jq -e --argjson count "$prompt_count" '
    .realistic_final_gate.passed == false and
    .fresh_response_validity.valid == false and
    .run_identity.prompt_count == $count and (.rows | length) == $count
  ' "$out/bench.json" >/dev/null 2>&1; then
  non_speed_die 'realistic benchmark semantic gate failed'
fi
[[ $bench_rc -eq 0 ]] || die "realistic benchmark was incomplete rc=$bench_rc"
printf 'bench_rc=0\n' >"$out/bench.status"
if jq -e --argjson count "$prompt_count" '
  (.rows | length) == $count and
  .fresh_response_validity.valid == true and
  .fresh_response_validity.cached_tokens_all_zero == true and
  .fresh_response_validity.return_token_ids_requested == true and
  .realistic_final_gate.passed == true and
  .realistic_final_gate.metric_events == 100 and
  .realistic_final_gate.metric_intervals == 99 and
  all(.rows[]; .cached_tokens == 0 and .metric_chunk_events_at_least_window == true and
      .metric_token_id_events_at_least_window == true and (.token_ids | length) >= 100)
' "$out/bench.json" >/dev/null; then
  :
else
  bench_gate_rc=$?
  if [[ $bench_gate_rc -eq 1 ]]; then
    non_speed_die 'benchmark final gate failed'
  fi
  die "benchmark final-gate checker failed with rc=$bench_gate_rc"
fi
curl -fsS "http://127.0.0.1:$port/metrics" >"$out/metrics.after.prom"

if [[ $quality == 1 ]]; then
  quality_args=(
    --base-url "http://127.0.0.1:$port" --model "$alias"
    --tokenizer "$model" --timeout 900 --repeat-runs 8
    --long-context-tokens 8192
    --request-id-prefix "qwen38-absolute-current-main-$lane-$port"
    --chat-template-kwargs-json '{"enable_thinking":false}'
    --output-json "$out/quality.json"
  )
  if [[ -n $quality_baseline_json ]]; then
    [[ -f $quality_baseline_json ]] || die "missing quality baseline: $quality_baseline_json"
    quality_args+=(--baseline-json "$quality_baseline_json")
  fi
  if [[ $quality_require_baseline == 1 ]]; then
    [[ -n $quality_baseline_json ]] || die 'required quality baseline is unset'
    quality_args+=(--require-baseline)
  fi
  if "$venv/bin/python" "$quality_helper" \
      "${quality_args[@]}" >"$out/quality.stdout.log" 2>&1; then
    quality_rc=0
  else
    quality_rc=$?
  fi
  if [[ $quality_rc -eq 1 ]] && jq -e \
      --argjson require_baseline "$quality_require_baseline" '
      (.pass_all | type) == "boolean" and
      (.exact_cases | length) == 7 and
      (.repeat_case.runs | length) == 8 and
      .long_context_case.requested_context_tokens == 8192 and
      ($require_baseline == 0 or (.baseline_comparisons | length) == 24) and
      (.pass_all == false or
        ($require_baseline == 1 and .baseline_match_all != true) or
        ($require_baseline == 0 and .baseline_match_all == false))
    ' "$out/quality.json" >/dev/null 2>&1; then
    non_speed_die 'quality battery or baseline semantic gate failed'
  fi
  [[ $quality_rc -eq 0 ]] || die "quality battery was incomplete rc=$quality_rc"
  printf 'quality_rc=0\n' >"$out/quality.status"
  require_jq_or_non_speed '
    .pass_all == true and (.exact_cases | length) == 7 and
    all(.exact_cases[]; .pass == true and
      .usage.prompt_tokens_details.cached_tokens == 0) and
    .repeat_case.pass == true and (.repeat_case.runs | length) == 8 and
    all(.repeat_case.runs[];
      .usage.prompt_tokens_details.cached_tokens == 0) and
    .long_context_case.pass == true and
    .long_context_case.requested_context_tokens == 8192 and
    .long_context_case.actual_prompt_tokens == 7617 and
    .long_context_case.usage.prompt_tokens_details.cached_tokens == 0
  ' "$out/quality.json" 'quality battery gate failed'
  if [[ $quality_require_baseline == 1 ]]; then
    require_jq_or_non_speed '
      .baseline_match_all == true and .baseline_status == "passed" and
      (.baseline_comparisons | length) == 24
    ' "$out/quality.json" 'quality baseline gate failed'
  fi
fi

capture_kernel_delta post-workload || die 'kernel rejected the timed or quality workload'
[[ $(</proc/sys/kernel/tainted) == 0 ]] ||
  die 'kernel became tainted during the timed or quality workload'

if [[ $cache_policy == seeded-fresh ]]; then
  best_config_manifest "$best_config_seed_target" \
    "$out/best-config-seed.final.sha256"
  cmp -s "$out/best-config-seed.source.sha256" \
    "$out/best-config-seed.final.sha256" ||
    die 'workload changed the seeded .best_config bundle'
  final_best_config_count=$(sudo -S -p '' find "$cache_dir" -type f \
    -name '*.best_config' <"$sudo_pass_file" | wc -l)
  [[ $final_best_config_count == "$expected_best_config_seed_count" ]] ||
    die "workload added unexpected .best_config records: $final_best_config_count"
fi

remove_owned_container || die 'failed to remove the invocation-owned server container'
capture_kernel_delta post-shutdown || die 'kernel rejected the model arm or shutdown'
kernel_taint_post=$(</proc/sys/kernel/tainted)
printf '%s\n' "$kernel_taint_post" >"$out/kernel-taint.post.txt"
[[ $kernel_taint_post == 0 ]] || die 'kernel became tainted during the model arm'
check_render_idle post || die 'render node remains held after container shutdown'
if [[ $cache_policy == seeded-fresh ]]; then
  best_config_manifest "$best_config_seed_target" \
    "$out/best-config-seed.postshutdown.sha256"
  cmp -s "$out/best-config-seed.source.sha256" \
    "$out/best-config-seed.postshutdown.sha256" ||
    die 'container shutdown changed the seeded .best_config bundle'
  postshutdown_best_config_count=$(sudo -S -p '' find "$cache_dir" -type f \
    -name '*.best_config' <"$sudo_pass_file" | wc -l)
  [[ $postshutdown_best_config_count == "$expected_best_config_seed_count" ]] ||
    die "container shutdown left unexpected .best_config records: $postshutdown_best_config_count"
fi
cache_manifest "$out/cache-manifest.post.sha256"
post_cache_manifest_sha256=$(sha256sum "$out/cache-manifest.post.sha256" | awk '{print $1}')
printf '%s\n' "$post_cache_manifest_sha256" >"$out/cache-manifest.post.sha256.digest"
if [[ $cache_policy == replay ]]; then
  if cmp -s "$out/cache-manifest.pre.sha256" \
      "$out/cache-manifest.post.sha256"; then
    :
  else
    replay_cmp_rc=$?
    if [[ $replay_cmp_rc -eq 1 ]]; then
      non_speed_die 'replay mutated the sealed compilation cache'
    fi
    die "replay cache comparison failed with rc=$replay_cmp_rc"
  fi
fi

remote_vllm_post=$(timeout --signal=TERM --kill-after=5s 30s \
  git ls-remote --exit-code https://github.com/vllm-project/vllm.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_kernel_post=$(timeout --signal=TERM --kill-after=5s 30s \
  git ls-remote --exit-code https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_base_post=$(timeout --signal=TERM --kill-after=5s 60s \
  sudo -S -p '' docker buildx imagetools inspect vllm/vllm-openai-xpu:nightly \
  --format '{{.Manifest.Digest}}' <"$sudo_pass_file")
printf '%s\n' "$remote_vllm_post" >"$out/upstream-vllm.post.txt"
printf '%s\n' "$remote_kernel_post" >"$out/upstream-kernel.post.txt"
printf '%s\n' "$remote_base_post" >"$out/upstream-nightly-base.post.txt"
if [[ $remote_vllm_post != "$vllm_head" ||
      $remote_kernel_post != "$kernel_head" ||
      $remote_base_post != "$base_digest" ]]; then
  printf 'stale-before-promotion\n' >"$out/final.status"
  exit 5
fi

printf 'pass\n' >"$out/final.status"
