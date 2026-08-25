#!/usr/bin/env bash
set -euo pipefail

script_path=$(realpath -e -- "${BASH_SOURCE[0]}")
script_dir=$(dirname -- "$script_path")
lane_dir=$(cd -- "$script_dir/.." && pwd)
repo_root=$(git -C "$lane_dir" rev-parse --show-toplevel)
dockerfile="$lane_dir/docker/Dockerfile.absolute-current-main"

vllm_source=${VLLM_SOURCE:-/home/steve/src/vllm-current-main}
kernel_source=${KERNEL_SOURCE:-/home/steve/src/vllm-xpu-kernels-current-main}
build_parent=${BUILD_PARENT:-/home/steve/builds}
archive_parent=${ARCHIVE_PARENT:-/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds}
kernel_artifact_dir=${KERNEL_ARTIFACT_DIR:-/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/upstream-kernel-1e90ffa6-artifact-9546354902}
sudo_password_file=${SUDO_PASSWORD_FILE:-/home/steve/SUDOPASSWORD.txt}

base_tag=vllm/vllm-openai-xpu:nightly
base_digest=sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876
base_image="vllm/vllm-openai-xpu@$base_digest"
vllm_upstream_url=https://github.com/vllm-project/vllm.git
kernel_upstream_url=https://github.com/vllm-project/vllm-xpu-kernels.git
base_kernel_version=0.1.13.2
kernel_run_id=32798686770
kernel_artifact_id=9546354902
kernel_artifact_name=vllm-xpu-kernels--20260825-014754
expected_kernel_artifact_digest=sha256:086116f01e838105167b4dfc408be0b3d4e924d7db9d616a0c00b67a69b24ecb
expected_kernel_artifact_size_bytes=344792738
expected_kernel_build_info_sha256=21d3850a885b1aa848016bd0e2330daafa6d083d6117ba6ea70a623afe6fb470
expected_kernel_wheel_sha256=f3d999060c11ad6db5b4033d50d19c6b665492380075480d041ec4ee58fdfeb6
expected_kernel_package_version=0.1.dev1+g1e90ffa67
rust_toolchain=1.95
expected_rust_toolchain_file_sha256=b75adb23d2a10ff0bfdbc436fa4e5e74347ec25eebfaa729a4344f01b59dccfe
expected_rust_cargo_lock_sha256=e975bb622cac4874694d7aa2d90cd34ab13a30d0426c32feead7b7c441c8219f
batch_invariant_config_path=vllm/model_executor/determinism/batch_invariant_configs.py
expected_batch_invariant_config_sha256=e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128
min_initial_root_free_kib=$((21 * 1024 * 1024))
min_lane_root_free_kib=$((8 * 1024 * 1024))

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat >&2 <<EOF
usage: $script_path --validate-only
       $script_path --build-control
       $script_path --build-both
       $script_path --build-all

Builds immutable zero-overlay images from literal upstream main:
  control: current vLLM + the official-base stock kernel
  both:    current vLLM + upstream's exact-current kernel artifact

The script never launches a GPU. By default, privileged Docker calls read the
local ignored password file documented in AGENTS.md. Set DOCKER_USE_SUDO=0
when the current user can access Docker directly.
EOF
}

[[ $# -eq 1 ]] || { usage; exit 2; }
mode=$1
case "$mode" in
  --validate-only|--build-control|--build-both|--build-all) ;;
  *) usage; exit 2 ;;
esac

for command_name in awk curl date find findmnt gh git grep jq realpath sed \
  sha256sum stat tar unzip; do
  command -v "$command_name" >/dev/null || die "$command_name is required"
done
[[ -f $dockerfile ]] || die "missing Dockerfile: $dockerfile"

docker_cmd() {
  if [[ ${DOCKER_USE_SUDO:-1} == 1 ]]; then
    if [[ -r $sudo_password_file ]]; then
      sudo -S -p '' docker "$@" <"$sudo_password_file"
    else
      sudo docker "$@"
    fi
  else
    docker "$@"
  fi
}

docker_cmd version >/dev/null || die 'Docker is not available'

assert_clean_main() {
  local tree=$1
  local label=$2
  [[ -d $tree/.git ]] || die "$label is not a Git clone: $tree"
  [[ $(git -C "$tree" branch --show-current) == main ]] ||
    die "$label must be on main"
  [[ -z $(git -C "$tree" status --porcelain=v1 --untracked-files=all) ]] ||
    die "$label must be completely clean: $tree"
}

live_remote_head() {
  local upstream_url=$1
  git ls-remote --exit-code "$upstream_url" refs/heads/main |
    awk 'NR == 1 {print $1}'
}

sync_literal_main() {
  local tree=$1
  local label=$2
  local upstream_url=$3
  local fetched_head local_head remote_head
  assert_clean_main "$tree" "$label"
  [[ $(git -C "$tree" remote get-url origin) == "$upstream_url" ]] ||
    die "$label origin is not the canonical upstream repository"
  git -C "$tree" fetch --prune "$upstream_url" \
    '+refs/heads/main:refs/remotes/origin/main'
  fetched_head=$(git -C "$tree" rev-parse refs/remotes/origin/main)
  remote_head=$(live_remote_head "$upstream_url")
  [[ $fetched_head == "$remote_head" ]] ||
    die "$label origin/main changed while resolving it"
  local_head=$(git -C "$tree" rev-parse HEAD)
  if [[ $local_head != "$remote_head" ]]; then
    git -C "$tree" merge --ff-only "$remote_head"
  fi
  assert_clean_main "$tree" "$label"
  [[ $(git -C "$tree" rev-parse HEAD) == "$remote_head" ]] ||
    die "$label did not fast-forward to literal upstream main"
}

assert_root_space() {
  local minimum_kib=$1
  local phase=$2
  local available
  available=$(df -Pk / | awk 'NR == 2 {print $4}')
  [[ $available =~ ^[0-9]+$ ]] || die 'could not read root free space'
  (( available >= minimum_kib )) ||
    die "root has insufficient free space for $phase (${available} KiB available; ${minimum_kib} KiB required)"
}

live_base_digest() {
  local token
  token=$(curl -fsSL \
    'https://auth.docker.io/token?service=registry.docker.io&scope=repository:vllm/vllm-openai-xpu:pull' |
    jq -er .token)
  curl -fsSI \
    -H "Authorization: Bearer $token" \
    -H 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' \
    "https://registry-1.docker.io/v2/vllm/vllm-openai-xpu/manifests/${base_tag##*:}" |
    tr -d '\r' | awk 'tolower($1) == "docker-content-digest:" {print $2}'
}

verify_base_image() {
  local image_id registry_digest
  registry_digest=$(live_base_digest)
  [[ $registry_digest == "$base_digest" ]] ||
    die "official nightly base advanced: $registry_digest != $base_digest; resolve and pin the new base before building"
  image_id=$(docker_cmd image inspect "$base_image" --format '{{.Id}}')
  [[ $image_id == "$base_digest" ]] ||
    die "base image ID mismatch: $image_id"
}

verify_rust_inputs() {
  [[ $(sha256sum "$vllm_source/rust-toolchain.toml" | awk '{print $1}') == \
    "$expected_rust_toolchain_file_sha256" ]] ||
    die 'Rust toolchain file changed; audit and repin before building'
  [[ $(sha256sum "$vllm_source/rust/Cargo.lock" | awk '{print $1}') == \
    "$expected_rust_cargo_lock_sha256" ]] ||
    die 'Rust Cargo.lock changed; audit and repin before building'
  [[ $(sed -n 's/^channel = "\([^"]*\)"$/\1/p' \
    "$vllm_source/rust-toolchain.toml") == "$rust_toolchain" ]] ||
    die 'Rust toolchain channel does not match the pinned value'
}

verify_source_batch_invariant_assets() {
  local required legacy
  for required in \
      vllm/model_executor/determinism/__init__.py \
      vllm/model_executor/determinism/batch_invariant.py \
      "$batch_invariant_config_path"; do
    [[ -f $vllm_source/$required ]] ||
      die "current source is missing batch-invariance asset: $required"
  done
  [[ $(sha256sum "$vllm_source/$batch_invariant_config_path" |
       awk '{print $1}') == "$expected_batch_invariant_config_sha256" ]] ||
    die 'current source batch-invariant config changed; audit before repinning'
  for legacy in \
      vllm/model_executor/layers/batch_invariant.py \
      vllm/model_executor/layers/batch_invariant_configs.py; do
    [[ ! -e $vllm_source/$legacy ]] ||
      die "current source retained a stale pre-refactor member: $legacy"
  done
}

verify_wheel_batch_invariant_assets() {
  local wheel=$1 required legacy
  for required in \
      vllm/model_executor/determinism/__init__.py \
      vllm/model_executor/determinism/batch_invariant.py \
      "$batch_invariant_config_path"; do
    unzip -Z1 "$wheel" | grep -Fx "$required" >/dev/null ||
      die "vLLM wheel is missing batch-invariance asset: $required"
  done
  [[ $(unzip -p "$wheel" "$batch_invariant_config_path" | sha256sum |
       awk '{print $1}') == "$expected_batch_invariant_config_sha256" ]] ||
    die 'vLLM wheel batch-invariant config hash mismatch'
  for legacy in \
      vllm/model_executor/layers/batch_invariant.py \
      vllm/model_executor/layers/batch_invariant_configs.py; do
    if unzip -Z1 "$wheel" | grep -Fx "$legacy" >/dev/null; then
      die "vLLM wheel contains a stale pre-refactor member: $legacy"
    fi
  done
}

wheel_metadata_value() {
  local wheel=$1
  local field=$2
  unzip -p "$wheel" '*/METADATA' |
    sed -n "s/^${field}: //p" | head -1
}

verify_official_kernel_artifact() {
  local expected_head=$1
  local api_result artifact_count artifact_result build_info wheel
  api_result=$(gh api "repos/vllm-project/vllm-xpu-kernels/actions/runs/$kernel_run_id")
  [[ $(jq -r .head_sha <<<"$api_result") == "$expected_head" ]] ||
    die 'official kernel run does not match literal kernel main'
  [[ $(jq -r .status <<<"$api_result") == completed ]] ||
    die 'official kernel run is not completed'
  [[ $(jq -r .conclusion <<<"$api_result") == success ]] ||
    die 'official kernel run did not succeed'

  artifact_count=$(gh api \
    "repos/vllm-project/vllm-xpu-kernels/actions/runs/$kernel_run_id/artifacts" \
    --jq "[.artifacts[] | select(.id == $kernel_artifact_id and .name == \"$kernel_artifact_name\" and .expired == false)] | length")
  [[ $artifact_count == 1 ]] || die 'exact official kernel artifact is absent or expired'
  artifact_result=$(gh api \
    "repos/vllm-project/vllm-xpu-kernels/actions/artifacts/$kernel_artifact_id")
  [[ $(jq -r .digest <<<"$artifact_result") == \
    "$expected_kernel_artifact_digest" ]] || die 'official kernel artifact digest mismatch'
  [[ $(jq -r .size_in_bytes <<<"$artifact_result") == \
    "$expected_kernel_artifact_size_bytes" ]] || die 'official kernel artifact size mismatch'
  [[ -d $kernel_artifact_dir ]] ||
    die "download the exact artifact into $kernel_artifact_dir"

  build_info="$kernel_artifact_dir/build_info.txt"
  [[ -f $build_info ]] || die "missing kernel build_info.txt: $build_info"
  [[ $(sha256sum "$build_info" | awk '{print $1}') == \
    "$expected_kernel_build_info_sha256" ]] || die 'kernel build_info hash mismatch'
  grep -Fx "Commit: $expected_head" "$build_info" >/dev/null ||
    die 'kernel build_info commit mismatch'
  grep -Fx 'Workflow: wheel-per-commit' "$build_info" >/dev/null ||
    die 'kernel build_info workflow mismatch'

  mapfile -t kernel_wheels < <(
    find "$kernel_artifact_dir" -type f -name '*.whl' -print
  )
  [[ ${#kernel_wheels[@]} -eq 1 ]] ||
    die 'kernel artifact must contain exactly one wheel'
  wheel=${kernel_wheels[0]}
  [[ $(sha256sum "$wheel" | awk '{print $1}') == \
    "$expected_kernel_wheel_sha256" ]] || die 'official kernel wheel hash mismatch'
  unzip -t "$wheel" >/dev/null || die 'kernel wheel ZIP integrity failed'
  [[ $(wheel_metadata_value "$wheel" Name) == vllm-xpu-kernels ]] ||
    die 'kernel wheel package name mismatch'
  [[ $(wheel_metadata_value "$wheel" Version) == \
    "$expected_kernel_package_version" ]] ||
    die 'unexpected official kernel wheel version'
  for member in \
    _C.abi3.so \
    _moe_C.abi3.so \
    _vllm_fa2_C.abi3.so \
    _xpu_C.abi3.so \
    libattn_kernels_xe_2.so \
    libgdn_attn_kernels_xe_2.so \
    libgrouped_gemm_xe_2.so \
    libgrouped_gemm_xe_default.so \
    libmhc_kernels_xe_2.so \
    libmqa_logits_kernels_xe_2.so \
    xpumem_allocator.abi3.so; do
    unzip -Z1 "$wheel" | grep -Fx "vllm_xpu_kernels/$member" >/dev/null ||
      die "kernel wheel is missing $member"
  done
  printf '%s\n' "$wheel"
}

assert_clean_main "$repo_root" 'lab repository'
sync_literal_main "$vllm_source" 'vLLM source' "$vllm_upstream_url"
sync_literal_main "$kernel_source" 'XPU-kernel source' "$kernel_upstream_url"
verify_base_image
assert_root_space "$min_initial_root_free_kib" 'the complete build'

vllm_head=$(git -C "$vllm_source" rev-parse HEAD)
vllm_tree=$(git -C "$vllm_source" rev-parse 'HEAD^{tree}')
kernel_head=$(git -C "$kernel_source" rev-parse HEAD)
kernel_tree=$(git -C "$kernel_source" rev-parse 'HEAD^{tree}')
lab_head=$(git -C "$repo_root" rev-parse HEAD)
lab_tree=$(git -C "$repo_root" rev-parse 'HEAD^{tree}')
build_script_sha256=$(sha256sum "$script_path" | awk '{print $1}')
dockerfile_sha256=$(sha256sum "$dockerfile" | awk '{print $1}')
vllm_short=${vllm_head:0:10}
kernel_short=${kernel_head:0:10}
verify_rust_inputs
verify_source_batch_invariant_assets

vllm_scm_version=$(docker_cmd run --rm --network=none \
  --entrypoint /opt/venv/bin/python \
  --mount "type=bind,src=$vllm_source,dst=/src/vllm,readonly" \
  -e GIT_CONFIG_COUNT=1 \
  -e GIT_CONFIG_KEY_0=safe.directory \
  -e GIT_CONFIG_VALUE_0=/src/vllm \
  "$base_image" -c \
  'from pathlib import Path; assert not Path("/dev/dri").exists(); from setuptools_scm import get_version; print(get_version(root="/src/vllm"))')
[[ $vllm_scm_version =~ ^[0-9A-Za-z.+]+$ ]] ||
  die "unexpected setuptools-scm version: $vllm_scm_version"
vllm_package_version="$vllm_scm_version.xpu"

kernel_wheel=
kernel_wheel_sha256=
kernel_package_version=
kernel_artifact_verified=false
if [[ $mode == --validate-only || $mode == --build-both || $mode == --build-all ]]; then
  kernel_wheel=$(verify_official_kernel_artifact "$kernel_head")
  kernel_wheel_sha256=$(sha256sum "$kernel_wheel" | awk '{print $1}')
  kernel_package_version=$(wheel_metadata_value "$kernel_wheel" Version)
  kernel_artifact_verified=true
fi

chunk_full="$kernel_source/csrc/xpu/attn/kernel_configs/chunk_prefill_full.conf"
paged_full="$kernel_source/csrc/xpu/attn/kernel_configs/paged_decode_full.conf"
[[ -f $chunk_full && -f $paged_full ]] || die 'current full kernel configs are absent'
chunk_full_sha256=$(sha256sum "$chunk_full" | awk '{print $1}')
paged_full_sha256=$(sha256sum "$paged_full" | awk '{print $1}')
workflow_sha256=$(sha256sum "$kernel_source/.github/workflows/wheel-per-commit.yaml" |
  awk '{print $1}')

printf 'PASS: literal current main resolved\n'
printf '  vLLM:       %s (tree %s)\n' "$vllm_head" "$vllm_tree"
printf '  XPU kernel: %s (tree %s)\n' "$kernel_head" "$kernel_tree"
printf '  base:       %s\n' "$base_image"
if [[ -n $kernel_wheel ]]; then
  printf '  kernel whl: %s (%s)\n' "$kernel_wheel_sha256" "$kernel_package_version"
fi

if [[ $mode == --validate-only ]]; then
  exit 0
fi

mkdir -p -- "$build_parent"
[[ $(findmnt -n -o FSTYPE --target "$build_parent") == ext4 ]] ||
  die 'live build scratch must be on ext4'
canonical_build_parent_root=$(realpath -e -- "$build_parent")

build_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
build_stamp=$(date -u +'%Y%m%dT%H%M%SZ')
build_root=${BUILD_ROOT:-$build_parent/qwen38-current-main-$build_stamp-$vllm_short-$kernel_short}
archive_dir="$archive_parent/$build_stamp-$vllm_short-$kernel_short"
[[ $build_root == /* ]] || die 'BUILD_ROOT must be absolute'
[[ ! -e $build_root ]] || die "BUILD_ROOT already exists: $build_root"
[[ ! -e $archive_dir ]] || die "archive destination exists: $archive_dir"
build_root_parent=$(dirname -- "$build_root")
build_root_leaf=$(basename -- "$build_root")
[[ -d $build_root_parent ]] || die "BUILD_ROOT parent is absent: $build_root_parent"
canonical_build_parent=$(realpath -e -- "$build_root_parent")
[[ $build_root == "$canonical_build_parent/$build_root_leaf" ]] ||
  die 'BUILD_ROOT must be canonical and have no symlinked parent components'
case "$build_root/" in
  "$canonical_build_parent_root/"*) ;;
  *) die 'BUILD_ROOT must be under the canonical BUILD_PARENT' ;;
esac
[[ $(findmnt -n -o FSTYPE --target "$canonical_build_parent") == ext4 ]] ||
  die 'the actual BUILD_ROOT parent must be on ext4'
case "$build_root" in
  /|/home|/home/steve|"$repo_root"|"$vllm_source"|"$kernel_source")
    die 'BUILD_ROOT is too broad or aliases a protected tree'
    ;;
esac
case "$build_root/" in
  "$repo_root/"*|"$vllm_source/"*|"$kernel_source/"*)
    die 'BUILD_ROOT must be outside the lab and source repositories'
    ;;
esac
mkdir -p -- \
  "$build_root/context/vllm-artifacts" \
  "$build_root/context/kernel-artifacts" \
  "$build_root/logs" \
  "$build_root/receipts" \
  "$build_root/vllm-source" \
  "$build_root/vllm-wheel"

vllm_archive="$build_root/vllm-source.tar"
git -C "$vllm_source" archive --format=tar --output="$vllm_archive" "$vllm_head"
vllm_archive_sha256=$(sha256sum "$vllm_archive" | awk '{print $1}')
tar -xf "$vllm_archive" -C "$build_root/vllm-source"

builder_name="q38-vllm-wheel-$vllm_short"
rust_fetch_name="q38-rust-fetch-$vllm_short"
if docker_cmd container inspect "$rust_fetch_name" >/dev/null 2>&1; then
  die "refusing to replace existing container $rust_fetch_name"
fi
if docker_cmd container inspect "$builder_name" >/dev/null 2>&1; then
  die "refusing to replace existing container $builder_name"
fi

# Fetch the exact Rust toolchain and Cargo.lock dependencies in a dedicated
# networked phase. Compilation and wheel assembly below are network-disabled.
docker_cmd run --rm --name "$rust_fetch_name" \
  --entrypoint /bin/bash \
  --mount "type=bind,src=$build_root,dst=/build" \
  "$base_image" -lc "
    set -euo pipefail
    cleanup() { chown -R $(id -u):$(id -g) /build; }
    trap cleanup EXIT
    test ! -e /dev/dri
    export CARGO_HOME=/build/cargo-home
    export RUSTUP_HOME=/build/rustup-home
    export PATH=\"\$CARGO_HOME/bin:\$PATH\"
    curl --proto '=https' --tlsv1.2 -fsS \
      -o /build/receipts/rustup-init \
      https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init
    curl --proto '=https' --tlsv1.2 -fsS \
      -o /build/receipts/rustup-init.sha256 \
      https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init.sha256
    cd /build/receipts
    sha256sum -c rustup-init.sha256
    chmod 0755 rustup-init
    ./rustup-init -y --profile minimal --default-toolchain '$rust_toolchain' \
      --no-modify-path
    rustup run '$rust_toolchain' rustc --version --verbose \
      >rustc-version.txt
    rustup run '$rust_toolchain' cargo --version --verbose \
      >cargo-version.txt
    cd /build/vllm-source
    rustup run '$rust_toolchain' cargo fetch --locked \
      --manifest-path rust/Cargo.toml
  " 2>&1 | tee "$build_root/logs/rust-locked-fetch.log"

docker_cmd run --rm --name "$builder_name" --network=none \
  --entrypoint /bin/bash \
  --mount "type=bind,src=$build_root,dst=/build" \
  "$base_image" -lc "
    set -euo pipefail
    cleanup() { chown -R $(id -u):$(id -g) /build; }
    trap cleanup EXIT
    test ! -e /dev/dri
    export CARGO_HOME=/build/cargo-home
    export RUSTUP_HOME=/build/rustup-home
    export RUSTUP_TOOLCHAIN='$rust_toolchain'
    export CARGO_NET_OFFLINE=true
    export PATH=\"\$CARGO_HOME/bin:\$PATH\"
    cd /build/vllm-source
    VLLM_RS_BUILD_VERSION='$vllm_package_version' \
      /opt/venv/bin/python tools/build_rust.py --release
    test -x vllm/_rust_tool_parser.abi3.so
    test -x vllm/vllm-rs
    VLLM_TARGET_DEVICE=xpu \\
    VLLM_REQUIRE_RUST_FRONTEND=1 \\
    VLLM_VERSION_OVERRIDE='$vllm_package_version' \\
    SETUPTOOLS_SCM_PRETEND_VERSION='$vllm_package_version' \\
      /root/.local/bin/uv build --offline --no-build-isolation --wheel \\
        --no-create-gitignore --python /opt/venv/bin/python \\
        --out-dir /build/vllm-wheel .
  " 2>&1 | tee "$build_root/logs/rust-and-vllm-wheel-build.log"

rustup_init_sha256=$(sha256sum "$build_root/receipts/rustup-init" |
  awk '{print $1}')
rust_extension_sha256=$(sha256sum \
  "$build_root/vllm-source/vllm/_rust_tool_parser.abi3.so" | awk '{print $1}')
rust_frontend_sha256=$(sha256sum \
  "$build_root/vllm-source/vllm/vllm-rs" | awk '{print $1}')

jq -n \
  --arg base_digest "$base_digest" \
  --arg batch_invariant_config_path "$batch_invariant_config_path" \
  --arg batch_invariant_config_sha256 "$expected_batch_invariant_config_sha256" \
  --arg build_script_sha256 "$build_script_sha256" \
  --arg build_utc "$build_utc" \
  --arg dockerfile_sha256 "$dockerfile_sha256" \
  --arg kernel_head "$kernel_head" \
  --arg kernel_tree "$kernel_tree" \
  --arg lab_head "$lab_head" \
  --arg lab_tree "$lab_tree" \
  --arg rust_cargo_lock_sha256 "$expected_rust_cargo_lock_sha256" \
  --arg rust_extension_sha256 "$rust_extension_sha256" \
  --arg rust_frontend_sha256 "$rust_frontend_sha256" \
  --arg rust_toolchain "$rust_toolchain" \
  --arg rust_toolchain_file_sha256 "$expected_rust_toolchain_file_sha256" \
  --arg rustup_init_sha256 "$rustup_init_sha256" \
  --arg vllm_archive_sha256 "$vllm_archive_sha256" \
  --arg vllm_head "$vllm_head" \
  --arg vllm_package_version "$vllm_package_version" \
  --arg vllm_tree "$vllm_tree" \
  '{
    schema: "neural-download-absolute-current-main-source-v2",
    state: "built-not-gpu-qualified",
    overlay: "none",
    build_utc: $build_utc,
    base_digest: $base_digest,
    lab: {head: $lab_head, tree: $lab_tree},
    build_inputs: {
      script_sha256: $build_script_sha256,
      dockerfile_sha256: $dockerfile_sha256
    },
    preserved_upstream_optimization_assets: {
      batch_invariant_config: {
        path: $batch_invariant_config_path,
        sha256: $batch_invariant_config_sha256
      }
    },
    vllm: {
      head: $vllm_head,
      tree: $vllm_tree,
      archive_sha256: $vllm_archive_sha256,
      package_version: $vllm_package_version
    },
    kernel: {head: $kernel_head, tree: $kernel_tree},
    rebuilt_rust: {
      toolchain: $rust_toolchain,
      toolchain_file_sha256: $rust_toolchain_file_sha256,
      cargo_lock_sha256: $rust_cargo_lock_sha256,
      rustup_init_sha256: $rustup_init_sha256,
      dependency_fetch_network: "enabled-lockfile-enforced",
      compile_network: "none-cargo-offline",
      extension_sha256: $rust_extension_sha256,
      frontend_sha256: $rust_frontend_sha256
    },
    performance_floors_tok_s: {
      tp1: {diagnostic: 30.2178, strict: 30.31067504052998},
      tp2: {diagnostic: 48.8301, strict: 49.01965141150585},
      tp4: {
        diagnostic: 71.5488,
        strict_floor: 71.29326283364946,
        required_repeat_high: 71.39843006187554
      }
    }
  }' >"$build_root/context/source-identity.json"

mapfile -t vllm_wheels < <(find "$build_root/vllm-wheel" -maxdepth 1 \
  -type f -name '*.whl' -print)
[[ ${#vllm_wheels[@]} -eq 1 ]] || die 'vLLM build did not produce exactly one wheel'
vllm_wheel=${vllm_wheels[0]}
unzip -t "$vllm_wheel" >/dev/null || die 'vLLM wheel ZIP integrity failed'
vllm_wheel_sha256=$(sha256sum "$vllm_wheel" | awk '{print $1}')
expected_vllm_metadata_version=$vllm_package_version
[[ $(wheel_metadata_value "$vllm_wheel" Name) == vllm ]] ||
  die 'vLLM wheel package name mismatch'
[[ $(wheel_metadata_value "$vllm_wheel" Version) == "$expected_vllm_metadata_version" ]] ||
  die 'vLLM wheel version mismatch'
[[ $(unzip -p "$vllm_wheel" 'vllm/_rust_tool_parser.abi3.so' | sha256sum |
  awk '{print $1}') == "$rust_extension_sha256" ]] ||
  die 'vLLM wheel Rust-extension hash mismatch'
[[ $(unzip -p "$vllm_wheel" 'vllm/vllm-rs' | sha256sum | awk '{print $1}') == \
  "$rust_frontend_sha256" ]] || die 'vLLM wheel Rust-frontend hash mismatch'
verify_wheel_batch_invariant_assets "$vllm_wheel"
install -m 0644 "$vllm_wheel" "$build_root/context/vllm-artifacts/"
touch "$build_root/context/kernel-artifacts/.stock-kernel"

build_image() {
  local lane=$1
  local install_current_kernel=$2
  local image_tag=$3
  local image_id static_preflight_sha256
  local lane_kernel_head lane_kernel_tree lane_kernel_version
  local lane_kernel_sha lane_chunk_sha lane_paged_sha

  if docker_cmd image inspect "$image_tag" >/dev/null 2>&1; then
    die "refusing to overwrite existing image tag $image_tag"
  fi

  if [[ $install_current_kernel == 1 ]]; then
    install -m 0644 "$kernel_wheel" "$build_root/context/kernel-artifacts/"
    lane_kernel_head=$kernel_head
    lane_kernel_tree=$kernel_tree
    lane_kernel_version=$kernel_package_version
    lane_kernel_sha=$kernel_wheel_sha256
    lane_chunk_sha=$chunk_full_sha256
    lane_paged_sha=$paged_full_sha256
  else
    [[ $(find "$build_root/context/kernel-artifacts" -maxdepth 1 -type f \
      -name '*.whl' | wc -l) -eq 0 ]] ||
      die 'control context unexpectedly contains a kernel wheel'
    touch "$build_root/context/kernel-artifacts/.stock-kernel"
    lane_kernel_head=stock-from-base
    lane_kernel_tree=stock-from-base
    lane_kernel_version=$base_kernel_version
    lane_kernel_sha=stock-from-base
    lane_chunk_sha=stock-from-base
    lane_paged_sha=stock-from-base
  fi

  assert_root_space "$min_lane_root_free_kib" "the $lane image"
  docker_cmd build --network=none --pull=false \
    --file "$dockerfile" \
    --tag "$image_tag" \
    --build-arg "BASE_IMAGE=$base_image" \
    --build-arg "BASE_DIGEST=$base_digest" \
    --build-arg "BATCH_INVARIANT_CONFIG_PATH=$batch_invariant_config_path" \
    --build-arg "BATCH_INVARIANT_CONFIG_SHA256=$expected_batch_invariant_config_sha256" \
    --build-arg "BUILD_SCRIPT_SHA256=$build_script_sha256" \
    --build-arg "BUILD_LANE=$lane" \
    --build-arg "BUILD_UTC=$build_utc" \
    --build-arg "DOCKERFILE_SHA256=$dockerfile_sha256" \
    --build-arg "INSTALL_CURRENT_KERNEL=$install_current_kernel" \
    --build-arg "KERNEL_CONFIG_CHUNK_SHA256=$lane_chunk_sha" \
    --build-arg "KERNEL_CONFIG_PAGED_SHA256=$lane_paged_sha" \
    --build-arg "KERNEL_HEAD=$lane_kernel_head" \
    --build-arg "KERNEL_PACKAGE_VERSION=$lane_kernel_version" \
    --build-arg "KERNEL_TREE=$lane_kernel_tree" \
    --build-arg "KERNEL_WHEEL_SHA256=$lane_kernel_sha" \
    --build-arg "LAB_HEAD=$lab_head" \
    --build-arg "LAB_TREE=$lab_tree" \
    --build-arg "RUST_EXTENSION_SHA256=$rust_extension_sha256" \
    --build-arg "RUST_FRONTEND_SHA256=$rust_frontend_sha256" \
    --build-arg "VLLM_ARCHIVE_SHA256=$vllm_archive_sha256" \
    --build-arg "VLLM_HEAD=$vllm_head" \
    --build-arg "VLLM_PACKAGE_VERSION=$vllm_package_version" \
    --build-arg "VLLM_TREE=$vllm_tree" \
    --build-arg "VLLM_WHEEL_SHA256=$vllm_wheel_sha256" \
    "$build_root/context" 2>&1 | tee "$build_root/logs/$lane-image-build.log"

  docker_cmd image inspect "$image_tag" >"$build_root/receipts/$lane-image-inspect.json"
  docker_cmd run --rm --network=none --entrypoint /bin/bash "$image_tag" \
    -lc 'cat /opt/neural-download/import-receipt.json; cat /opt/neural-download/pip-check.txt' \
    >"$build_root/receipts/$lane-static-preflight.txt"
  printf '%s\n' "$image_tag" >"$build_root/receipts/$lane-image-tag.txt"

  image_id=$(jq -r '.[0].Id' "$build_root/receipts/$lane-image-inspect.json")
  [[ $image_id =~ ^sha256:[0-9a-f]{64}$ ]] ||
    die "invalid built image ID for $lane: $image_id"
  [[ $(docker_cmd image inspect "$image_tag" --format '{{.Id}}') == "$image_id" ]] ||
    die "built image tag moved before receipt capture: $image_tag"
  static_preflight_sha256=$(sha256sum \
    "$build_root/receipts/$lane-static-preflight.txt" | awk '{print $1}')
  case "$lane" in
    current-vllm-stock-kernel)
      control_image_id=$image_id
      control_static_preflight_sha256=$static_preflight_sha256
      ;;
    both-current-zero-overlay)
      both_image_id=$image_id
      both_static_preflight_sha256=$static_preflight_sha256
      ;;
    *) die "unknown build lane: $lane" ;;
  esac
}

control_tag="neural-download/vllm-openai-xpu:vllm-$vllm_short-kernel-stock-$base_digest"
control_tag=${control_tag//sha256:/}
both_tag="neural-download/vllm-openai-xpu:vllm-$vllm_short-kernel-$kernel_short-official"

control_built=false
both_built=false
control_image_id=
control_static_preflight_sha256=
both_image_id=
both_static_preflight_sha256=
if [[ $mode == --build-control || $mode == --build-all ]]; then
  build_image current-vllm-stock-kernel 0 "$control_tag"
  control_built=true
fi
if [[ $mode == --build-both || $mode == --build-all ]]; then
  build_image both-current-zero-overlay 1 "$both_tag"
  both_built=true
fi

# A moving upstream head never silently changes an identity already built in
# this run. If main advanced while artifacts were being built, preserve these
# dated artifacts as stale-before-qualification and start a new update.
[[ $(live_remote_head "$vllm_upstream_url") == "$vllm_head" ]] ||
  die 'vLLM main advanced during the build; do not qualify these images'
[[ $(live_remote_head "$kernel_upstream_url") == "$kernel_head" ]] ||
  die 'kernel main advanced during the build; do not qualify these images'
[[ $(live_base_digest) == "$base_digest" ]] ||
  die 'official nightly base advanced during the build; do not qualify these images'

jq -n \
  --arg archive_dir "$archive_dir" \
  --arg base_digest "$base_digest" \
  --arg batch_invariant_config_path "$batch_invariant_config_path" \
  --arg batch_invariant_config_sha256 "$expected_batch_invariant_config_sha256" \
  --arg build_script_sha256 "$build_script_sha256" \
  --arg build_root "$build_root" \
  --arg build_utc "$build_utc" \
  --arg mode "$mode" \
  --arg chunk_full_sha256 "$chunk_full_sha256" \
  --arg control_image_id "$control_image_id" \
  --arg control_static_preflight_sha256 "$control_static_preflight_sha256" \
  --arg control_tag "$control_tag" \
  --arg dockerfile_sha256 "$dockerfile_sha256" \
  --arg kernel_artifact_name "$kernel_artifact_name" \
  --arg kernel_artifact_digest "$expected_kernel_artifact_digest" \
  --arg kernel_head "$kernel_head" \
  --arg kernel_package_version "$kernel_package_version" \
  --arg kernel_tree "$kernel_tree" \
  --arg kernel_wheel_sha256 "$kernel_wheel_sha256" \
  --arg lab_head "$lab_head" \
  --arg lab_tree "$lab_tree" \
  --arg paged_full_sha256 "$paged_full_sha256" \
  --arg rust_cargo_lock_sha256 "$expected_rust_cargo_lock_sha256" \
  --arg rust_extension_sha256 "$rust_extension_sha256" \
  --arg rust_frontend_sha256 "$rust_frontend_sha256" \
  --arg rust_toolchain "$rust_toolchain" \
  --arg rust_toolchain_file_sha256 "$expected_rust_toolchain_file_sha256" \
  --arg rustup_init_sha256 "$rustup_init_sha256" \
  --arg vllm_archive_sha256 "$vllm_archive_sha256" \
  --arg vllm_head "$vllm_head" \
  --arg vllm_package_version "$expected_vllm_metadata_version" \
  --arg vllm_tree "$vllm_tree" \
  --arg vllm_wheel_sha256 "$vllm_wheel_sha256" \
  --arg workflow_sha256 "$workflow_sha256" \
  --arg both_image_id "$both_image_id" \
  --arg both_static_preflight_sha256 "$both_static_preflight_sha256" \
  --arg both_tag "$both_tag" \
  --argjson kernel_artifact_id "$kernel_artifact_id" \
  --argjson kernel_artifact_size_bytes "$expected_kernel_artifact_size_bytes" \
  --argjson kernel_run_id "$kernel_run_id" \
  --argjson both_built "$both_built" \
  --argjson control_built "$control_built" \
  --argjson kernel_artifact_verified "$kernel_artifact_verified" \
  '{
    schema: "neural-download-absolute-current-main-build-v2",
    state: "static-preflight-passed-for-built-images-gpu-qualification-pending",
    mode: $mode,
    overlay: "none",
    build_utc: $build_utc,
    build_root: $build_root,
    external_archive: $archive_dir,
    base_digest: $base_digest,
    lab: {head: $lab_head, tree: $lab_tree},
    build_inputs: {
      script_sha256: $build_script_sha256,
      dockerfile_sha256: $dockerfile_sha256
    },
    preserved_upstream_optimization_assets: {
      batch_invariant_config: {
        path: $batch_invariant_config_path,
        sha256: $batch_invariant_config_sha256
      }
    },
    rebuilt_rust: {
      toolchain: $rust_toolchain,
      toolchain_file_sha256: $rust_toolchain_file_sha256,
      cargo_lock_sha256: $rust_cargo_lock_sha256,
      rustup_init_sha256: $rustup_init_sha256,
      dependency_fetch_network: "enabled-lockfile-enforced",
      compile_network: "none-cargo-offline",
      extension_sha256: $rust_extension_sha256,
      frontend_sha256: $rust_frontend_sha256
    },
    vllm: {
      head: $vllm_head,
      tree: $vllm_tree,
      package_version: $vllm_package_version,
      source_archive_sha256: $vllm_archive_sha256,
      wheel_sha256: $vllm_wheel_sha256
    },
    kernel: {
      head: $kernel_head,
      tree: $kernel_tree,
      package_version: (if $kernel_artifact_verified then $kernel_package_version else null end),
      official_artifact: (if $kernel_artifact_verified then {
          run_id: $kernel_run_id,
          artifact_id: $kernel_artifact_id,
          name: $kernel_artifact_name,
          archive_digest: $kernel_artifact_digest,
          archive_size_bytes: $kernel_artifact_size_bytes,
          wheel_sha256: $kernel_wheel_sha256,
          workflow_sha256: $workflow_sha256,
          chunk_prefill_full_sha256: $chunk_full_sha256,
          paged_decode_full_sha256: $paged_full_sha256
        } else null end)
    },
    images: {
      current_vllm_stock_kernel: {
        built: $control_built,
        tag: (if $control_built then $control_tag else null end),
        image_id: (if $control_built then $control_image_id else null end),
        static_preflight_passed: $control_built,
        static_preflight_sha256: (if $control_built then $control_static_preflight_sha256 else null end)
      },
      both_current_zero_overlay: {
        built: $both_built,
        tag: (if $both_built then $both_tag else null end),
        image_id: (if $both_built then $both_image_id else null end),
        static_preflight_passed: $both_built,
        static_preflight_sha256: (if $both_built then $both_static_preflight_sha256 else null end)
      }
    },
    promotion: {
      qualified: false,
      order: [
        "current-vLLM/stock-kernel TP1",
        "both-current zero-overlay TP1",
        "both-current accepted-overlay TP1",
        "TP2",
        "TP4"
      ],
      rule: "Never replace a certified result unless identity, quality, and performance floors all pass."
    }
  }' >"$build_root/receipts/build-receipt.json"

mkdir -p -- "$archive_dir"
cp -- "$vllm_wheel" "$archive_dir/"
cp -- "$build_root/receipts/build-receipt.json" "$archive_dir/"
cp -- "$build_root/context/source-identity.json" "$archive_dir/"
cp -- "$script_path" "$archive_dir/"
cp -- "$dockerfile" "$archive_dir/"
find "$build_root/receipts" -maxdepth 1 -type f ! -name build-receipt.json \
  -exec cp -t "$archive_dir" -- {} +
find "$build_root/logs" -maxdepth 1 -type f \
  -exec cp -t "$archive_dir" -- {} +
(
  cd "$archive_dir"
  find . -maxdepth 1 -type f ! -name SHA256SUMS -printf '%P\n' |
    sort | xargs -r sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS
)

[[ $(live_remote_head "$vllm_upstream_url") == "$vllm_head" ]] ||
  die 'vLLM main advanced while archiving; do not qualify these images'
[[ $(live_remote_head "$kernel_upstream_url") == "$kernel_head" ]] ||
  die 'kernel main advanced while archiving; do not qualify these images'
[[ $(live_base_digest) == "$base_digest" ]] ||
  die 'official nightly base advanced while archiving; do not qualify these images'

printf 'PASS: static current-main build completed; GPU qualification is still pending.\n'
printf '  build root: %s\n' "$build_root"
printf '  archive:    %s\n' "$archive_dir"
if [[ $mode == --build-control || $mode == --build-all ]]; then
  printf '  control:    %s\n' "$control_tag"
fi
if [[ $mode == --build-both || $mode == --build-all ]]; then
  printf '  both-head:  %s\n' "$both_tag"
fi
