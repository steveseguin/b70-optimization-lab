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
# CACHE_POLICY: fresh or replay. Replay additionally requires
# EXPECTED_CACHE_MANIFEST_SHA256.

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
cache_policy=${CACHE_POLICY:?set CACHE_POLICY=fresh or replay}
max_tokens=${MAX_TOKENS:-512}
bench=${BENCH:-1}
canary=${CANARY:-1}
natural_eos=${NATURAL_EOS:-0}
return_token_ids=${RETURN_TOKEN_IDS:-1}
quality=${QUALITY:-0}
quality_require_baseline=${QUALITY_REQUIRE_BASELINE:-0}
quality_baseline_json=${QUALITY_BASELINE_JSON:-}
graph=${VLLM_XPU_GRAPH:-1}
pythonhashseed=${PYTHONHASHSEED:-0}
sudo_pass_file=${SUDO_PASS_FILE:-/home/steve/SUDOPASSWORD.txt}
legacy_lock_file=/tmp/b70-benchmark.lock
muse_lock_file=/run/lock/muse-glimmer-gpu-exclusive.lock
expected_gpu0_bdf=0000:23:00.0
expected_gpu0_uuid=00000000-0000-0023-0000-0000e2238086
created_container_id=
container_id_file=
container_removal_complete=0

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

dockerc() {
  sudo -S -p '' docker "$@" <"$sudo_pass_file"
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
  [[ $fd =~ ^[0-9]+$ ]] || die "invalid inherited lock descriptor: $fd"
  [[ -e /proc/$$/fd/$fd ]] || die "inherited lock descriptor $fd is closed"
  local actual_path
  actual_path=$(readlink -f -- "/proc/$$/fd/$fd")
  [[ $actual_path == "$(readlink -f -- "$expected_path")" ]] ||
    die "inherited lock path mismatch: $actual_path != $expected_path"
  flock -n "$fd" || die "inherited lock is not exclusively held: $expected_path"
}

[[ $lane == control || $lane == both ]] || die 'LANE must be control or both'
[[ $mtp =~ ^[0-9]+$ ]] || die 'MTP must be a nonnegative integer'
[[ $kv == f16 || $kv == fp8_e4m3 || $kv == fp8_e5m2 ]] ||
  die 'KV must be f16, fp8_e4m3, or fp8_e5m2'
[[ $maxlen =~ ^[1-9][0-9]*$ ]] || die 'MAXLEN must be a positive integer'
[[ $gpu =~ ^[0-3](,[0-3])*$ ]] || die 'GPUS must be a comma-separated subset of 0..3'
[[ $port =~ ^[1-9][0-9]*$ && $port -le 65535 ]] || die 'invalid PORT'
[[ $cache_policy == fresh || $cache_policy == replay ]] ||
  die 'CACHE_POLICY must be fresh or replay'
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
[[ $pythonhashseed == 0 ]] || die 'this strict promotion runner requires PYTHONHASHSEED=0'
[[ -z ${EXTRA_VLLM_ARGS:-} ]] || die 'EXTRA_VLLM_ARGS is forbidden in zero-overlay qualification'
[[ -z ${PROMPT_IDS:-} ]] || die 'strict qualification requires the complete suite'
[[ -z ${ONEAPI_DEVICE_SELECTOR:-} ]] || die 'ONEAPI_DEVICE_SELECTOR must be unset'
[[ -z ${ZE_AFFINITY_MASK:-} ]] || die 'inherited ZE_AFFINITY_MASK must be unset'
[[ -z ${XPU_GRAPH:-} ]] || die 'inherited XPU_GRAPH must be unset'
[[ -z ${COMPILATION_CONFIG:-} ]] || die 'inherited COMPILATION_CONFIG must be unset'
[[ -z ${PYTHONPATH:-} ]] || die 'inherited PYTHONPATH must be unset'
[[ -z ${LD_PRELOAD:-} ]] || die 'inherited LD_PRELOAD must be unset'
[[ -z ${VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE:-} ]] ||
  die 'autotune isolation flags are forbidden in zero-overlay qualification'
[[ -z ${VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING:-} ]] ||
  die 'autotune isolation flags are forbidden in zero-overlay qualification'
[[ -z ${TRITON_CACHE_AUTOTUNING:-} ]] ||
  die 'autotune isolation flags are forbidden in zero-overlay qualification'

while IFS='=' read -r variable _; do
  case $variable in
    VLLM_XPU_GRAPH) ;;
    VLLM_XPU_*|VLLM_INTEL_*|VLLM_USE_*|VLLM_FORCE_*|CCL_*|ONECCL_*)
      die "inherited experiment variable is forbidden: $variable"
      ;;
  esac
done < <(env)

[[ -r $sudo_pass_file ]] || die "sudo password file is unreadable: $sudo_pass_file"
for command_name in curl find findmnt flock fuser git jq realpath sha256sum ss tr xpu-smi; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
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
[[ -z $(git -C "$repo" status --porcelain=v1 --untracked-files=all) ]] ||
  die 'lab repository must be completely clean'
[[ $(git -C "$repo" branch --show-current) == main ]] || die 'lab repository must be on main'
[[ $(git -C "$repo" rev-parse HEAD) == "$(git -C "$repo" rev-parse origin/main)" ]] ||
  die 'local main must equal origin/main'
live_lab_main=$(git -C "$repo" ls-remote --exit-code origin refs/heads/main |
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

[[ -z $(dockerc ps -q) ]] || die 'a Docker container is already running'
if dockerc container inspect "$name" >/dev/null 2>&1; then
  die "refusing to replace pre-existing container: $name"
fi
pgrep -af 'EngineCore|vllm serve|llama-server' | grep -v pgrep >/dev/null &&
  die 'a model server process is already running'
ss -ltnH "sport = :$port" | grep -q . && die "port $port already has a listener"

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
remote_vllm_pre=$(git ls-remote --exit-code https://github.com/vllm-project/vllm.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_kernel_pre=$(git ls-remote --exit-code https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_base_pre=$(dockerc buildx imagetools inspect vllm/vllm-openai-xpu:nightly \
  --format '{{.Manifest.Digest}}')
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

"$model_verifier" "$model_manifest" "$model" \
  --json "$out/model-direct-and-ordinary-verify.json" \
  >"$out/model-direct-and-ordinary-verify.log" 2>&1 ||
  die 'model direct-and-ordinary identity verification failed'
jq -e '.status == "verified" and (.files | length) == 19 and all(.files[]; .ok == true)' \
  "$out/model-direct-and-ordinary-verify.json" >/dev/null ||
  die 'model verifier did not certify all 19 files'
sha256sum "$model_manifest" "$suite" \
  "$bench_helper" "$quality_helper" "$model_verifier" "$script_path" \
  >"$out/input-files.sha256"
uname -a >"$out/host-uname.txt"
ls -l /dev/dri/by-path >"$out/host-dri-by-path.txt"

discovery_json=$(xpu-smi discovery -j 2>/dev/null) || die 'xpu-smi discovery failed'
printf '%s\n' "$discovery_json" >"$out/xpu-smi-discovery.json"
jq -e --arg bdf "$expected_gpu0_bdf" --arg uuid "$expected_gpu0_uuid" '
  ([.device_list[] | select(.device_name | contains("Arc(TM) Pro B70"))] | length) == 4 and
  ([.device_list[] | select(.device_id == 0)] | length) == 1 and
  any(.device_list[];
    .device_id == 0 and .pci_bdf_address == $bdf and .uuid == $uuid)
' "$out/xpu-smi-discovery.json" >/dev/null || die 'GPU0 BDF/UUID identity changed'
mapfile -t render_nodes < <(find /dev/dri -maxdepth 1 -type c -name 'renderD*' -print | sort)
[[ ${#render_nodes[@]} -eq 4 ]] || die 'expected exactly four render nodes'
set +e
render_holders=$(sudo -S -p '' fuser "${render_nodes[@]}" 2>/dev/null <"$sudo_pass_file")
render_fuser_rc=$?
set -e
[[ $render_fuser_rc -eq 1 ]] || {
  [[ $render_fuser_rc -ne 0 ]] || die 'a process already holds a render node'
  die "render-node holder scan failed with rc=$render_fuser_rc"
}
[[ -z $render_holders ]] || die 'render-node holder scan returned unexpected output'
gpu0_render_node=$(realpath -e -- "/dev/dri/by-path/pci-$expected_gpu0_bdf-render")
[[ $gpu0_render_node == /dev/dri/renderD* ]] || die 'GPU0 render-node mapping changed'
printf 'ordinal=0\nbdf=%s\nuuid=%s\nrender_node=%s\n' \
  "$expected_gpu0_bdf" "$expected_gpu0_uuid" "$gpu0_render_node" \
  >"$out/gpu0-device-identity.env"

if [[ $cache_policy == fresh ]]; then
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
  printf 'max_tokens=%s\nbench=%s\ncanary=%s\nnatural_eos=%s\n' \
    "$max_tokens" "$bench" "$canary" "$natural_eos"
  printf 'return_token_ids=%s\nquality=%s\nquality_require_baseline=%s\n' \
    "$return_token_ids" "$quality" "$quality_require_baseline"
  printf 'quality_baseline_json=%s\n' "${quality_baseline_json:-unset}"
  if [[ -n $quality_baseline_json ]]; then
    printf 'quality_baseline_sha256=%s\n' \
      "$(sha256sum "$quality_baseline_json" | awk '{print $1}')"
  fi
  printf 'vllm_xpu_enable_xpu_graph=%s\npythonhashseed=%s\n' "$graph" "$pythonhashseed"
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
  local cleanup_failed=0
  local cleanup_manifest_sha256
  trap - EXIT INT TERM HUP
  remove_owned_container || cleanup_failed=1
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
        cmp -s "$out/cache-manifest.pre.sha256" "$out/cache-manifest.post.sha256" ||
          cleanup_failed=1
      fi
    fi
  fi
  if [[ $cleanup_failed == 1 ]]; then
    printf 'fail-cleanup body_rc=%s\n' "$rc" >"$out/final.status"
    exit 7
  fi
  if [[ ! -f $out/final.status ]]; then
    [[ $rc -ne 0 ]] || rc=1
    printf 'fail rc=%s\n' "$rc" >"$out/final.status"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

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
  -e PYTHONHASHSEED=0 \
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
for expected_env in \
  CCL_ZE_IPC_EXCHANGE=sockets \
  PYTHONHASHSEED=0 \
  VLLM_CACHE_ROOT=/run-cache/vllm \
  VLLM_NO_USAGE_STATS=1 \
  VLLM_XPU_ENABLE_XPU_GRAPH=1 \
  XDG_CACHE_HOME=/run-cache/xdg \
  ZE_AFFINITY_MASK=0; do
  grep -Fx "$expected_env" "$out/container-environment.txt" >/dev/null ||
    die "required container environment is absent: $expected_env"
done
awk -F= '
  {reject=0}
  $1 ~ /^VLLM_XPU_/ && $1 != "VLLM_XPU_ENABLE_XPU_GRAPH" {reject=1}
  $1 ~ /^(VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE|VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING|TRITON_CACHE_AUTOTUNING)$/ {reject=1}
  $1 ~ /^(ONEAPI_DEVICE_SELECTOR|XPU_GRAPH|COMPILATION_CONFIG|PYTHONPATH|LD_PRELOAD)$/ {reject=1}
  $1 ~ /^(CCL_|ONECCL_)/ && $1 != "CCL_ZE_IPC_EXCHANGE" {reject=1}
  reject {print > "/dev/stderr"; bad=1}
  END {exit bad ? 1 : 0}
' "$out/container-environment.txt" || die 'forbidden experiment environment reached the container'

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
  grep -Fq "$cli_field" "$out/effective-cli-config.txt" ||
    die "effective CLI config is missing: $cli_field"
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
  grep -Fq "$engine_field" "$out/effective-engine-config.txt" ||
    die "effective engine config is missing: $engine_field"
done
grep -Fq 'Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)' "$out/server-startup.log" ||
  die 'PIECEWISE graph capture marker is absent'
grep -Fq 'Capturing CUDA graphs (decode, FULL)' "$out/server-startup.log" ||
  die 'FULL graph capture marker is absent'
grep -Fq 'Graph capturing finished' "$out/server-startup.log" ||
  die 'graph capture completion marker is absent'

"$venv/bin/python" - "http://127.0.0.1:$port" "$alias" "$out/canary.json" <<'PY'
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
printf 'canary_rc=0\n' >"$out/canary.status"

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
"$venv/bin/python" "$bench_helper" \
  "${bench_args[@]}" >"$out/bench.stdout.log" 2>&1
printf 'bench_rc=0\n' >"$out/bench.status"
prompt_count=$(jq '.prompts | length' "$suite")
jq -e --argjson count "$prompt_count" '
  (.rows | length) == $count and
  .fresh_response_validity.valid == true and
  .fresh_response_validity.cached_tokens_all_zero == true and
  .fresh_response_validity.return_token_ids_requested == true and
  .realistic_final_gate.passed == true and
  .realistic_final_gate.metric_events == 100 and
  .realistic_final_gate.metric_intervals == 99 and
  all(.rows[]; .cached_tokens == 0 and .metric_chunk_events_at_least_window == true and
      .metric_token_id_events_at_least_window == true and (.token_ids | length) >= 100)
' "$out/bench.json" >/dev/null || die 'benchmark final gate failed'
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
  "$venv/bin/python" "$quality_helper" \
    "${quality_args[@]}" >"$out/quality.stdout.log" 2>&1
  printf 'quality_rc=0\n' >"$out/quality.status"
  jq -e '
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
  ' "$out/quality.json" >/dev/null || die 'quality battery gate failed'
  if [[ $quality_require_baseline == 1 ]]; then
    jq -e '
      .baseline_match_all == true and .baseline_status == "passed" and
      (.baseline_comparisons | length) == 24
    ' "$out/quality.json" >/dev/null || die 'quality baseline gate failed'
  fi
fi

remove_owned_container || die 'failed to remove the invocation-owned server container'
cache_manifest "$out/cache-manifest.post.sha256"
post_cache_manifest_sha256=$(sha256sum "$out/cache-manifest.post.sha256" | awk '{print $1}')
printf '%s\n' "$post_cache_manifest_sha256" >"$out/cache-manifest.post.sha256.digest"
if [[ $cache_policy == replay ]]; then
  cmp -s "$out/cache-manifest.pre.sha256" "$out/cache-manifest.post.sha256" ||
    die 'replay mutated the sealed compilation cache'
fi

remote_vllm_post=$(git ls-remote --exit-code https://github.com/vllm-project/vllm.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_kernel_post=$(git ls-remote --exit-code https://github.com/vllm-project/vllm-xpu-kernels.git refs/heads/main |
  awk 'NR == 1 {print $1}')
remote_base_post=$(dockerc buildx imagetools inspect vllm/vllm-openai-xpu:nightly \
  --format '{{.Manifest.Digest}}')
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
