#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
kernels=/home/steve/src/vllm-xpu-kernels
vllm=/home/steve/src/vllm-current-main
builder="${repo}/scripts/build-vllm-xpu-kernels-xpu-c-only.sh"
old_stage=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70/vllm_xpu_kernels
old_manifest="${repo}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256"
build_dir=/mnt/fast-ai/qwen38-build/build-xpu-serving-eeee7d6-a1
install_prefix=/mnt/fast-ai/qwen38-build/install-xpu-serving-eeee7d6-a1
stage_root=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a1
stage="${stage_root}/vllm_xpu_kernels"
evidence=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a1-evidence
fetchcontent=/mnt/fast-ai/qwen38-build/deps-xpu-serving-eeee7d6-a1

expected_builder=5cbdadc200626ed9da03b6aa4808a59ee848348c671ce76d4d7ada4a37ca464f
expected_old_manifest=9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b
expected_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_kernels=eeee7d671abfa964626baa18da2174bb92cac80a
expected_kernel_chain=$'eeee7d671abfa964626baa18da2174bb92cac80a\n042c6e877b667f03087091ce3ab58b80903afc20\na6ee94fd8fadb97dc033921f1019ef18f14d5dd0\n359466a262489bdf4e1774e3572202dc82a00718\nad25aa9f69a2171612b9c6b83dfa82c69559f9e4'
topk_patch="${repo}/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0006-perf-moe-skip-unused-512-expert-top-k-workspace.patch"
grouped_patch="${repo}/patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0007-fix-grouped-gemm-build-contracts.patch"
expected_topk_patch=d4a7d9934e21a37ed21e812355e4241690992d5b81c27fe818dc9302f19d0ef9
expected_grouped_patch=4126ebd2057173128fa5332646cc256d7f5daaa625ec86c18241fbc63e71a194
expected_patchelf=35fc95654387035338a74bb8cf62fde3712ec83dd8ca30a768deb714d07f063a
expected_sycl=0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f
onednn=/home/steve/src/vllm-xpu-kernels/.deps/onednn-src
cutlass=/home/steve/src/vllm-xpu-kernels/.deps/cutlass-sycl-src
expected_onednn=80afa71049cd69a3df32adcccb623b12cd7baa22
expected_cutlass=cd763790ad2f74d7294435ecf77682bac0062c3a
expected_cmake=fe8b875f09a5adf3cf1b995d0fe7ddf60fe7566c7d4bc0edf5d79a772b5a4403
expected_ninja=696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67
expected_icx=766ffc69a39b16268e022744b74c15bf747f120eb55a4f3628148d025023f968
expected_python=202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

check_source_closure() {
  [[ "$(sha256sum "$builder" | cut -d' ' -f1)" == "$expected_builder" ]] || fail "builder changed"
  [[ "$(sha256sum "$old_manifest" | cut -d' ' -f1)" == "$expected_old_manifest" ]] || fail "old manifest changed"
  [[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head changed"
  [[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM has tracked changes"
  [[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" ]] || fail "kernel head changed"
  [[ "$(git -C "$kernels" rev-list --max-count=5 HEAD)" == "$expected_kernel_chain" ]] || fail "kernel source chain changed"
  [[ -z "$(git -C "$kernels" status --porcelain --untracked-files=no)" ]] || fail "kernel source has tracked changes"
  [[ "$(git -C "$kernels" status --porcelain)" == '?? third_party/' ]] || fail "unexpected untracked kernel-source content"
  [[ "$(git -C "$onednn" rev-parse HEAD)" == "$expected_onednn" ]] || fail "oneDNN source head changed"
  [[ -z "$(git -C "$onednn" status --porcelain --untracked-files=no)" ]] || fail "oneDNN source has tracked changes"
  [[ "$(git -C "$cutlass" rev-parse HEAD)" == "$expected_cutlass" ]] || fail "SYCL-TLA source head changed"
  [[ -z "$(git -C "$cutlass" status --porcelain --untracked-files=no)" ]] || fail "SYCL-TLA source has tracked changes"
  [[ "$(sha256sum "$topk_patch" | cut -d' ' -f1)" == "$expected_topk_patch" ]] || fail "top-k patch changed"
  [[ "$(sha256sum "$grouped_patch" | cut -d' ' -f1)" == "$expected_grouped_patch" ]] || fail "grouped-build patch changed"
  [[ "$(sha256sum /usr/bin/patchelf | cut -d' ' -f1)" == "$expected_patchelf" ]] || fail "patchelf changed"
  [[ "$(patchelf --version)" == 'patchelf 0.18.0' ]] || fail "patchelf version changed"
  [[ "$(sha256sum /home/steve/.local/bin/cmake | cut -d' ' -f1)" == "$expected_cmake" ]] || fail "CMake changed"
  [[ "$(cmake --version | head -1)" == 'cmake version 4.3.2' ]] || fail "CMake version changed"
  [[ "$(sha256sum /home/steve/.local/bin/ninja | cut -d' ' -f1)" == "$expected_ninja" ]] || fail "Ninja changed"
  [[ "$(ninja --version)" == '1.13.0.git.kitware.jobserver-pipe-1' ]] || fail "Ninja version changed"
  [[ "$(sha256sum /opt/intel/oneapi/compiler/2025.3/bin/icx | cut -d' ' -f1)" == "$expected_icx" ]] || fail "oneAPI compiler changed"
  [[ "$(/opt/intel/oneapi/compiler/2025.3/bin/icx --version | head -1)" == 'Intel(R) oneAPI DPC++/C++ Compiler 2025.3.3 (2025.3.3.20260319)' ]] || fail "oneAPI compiler version changed"
  [[ "$(sha256sum /home/steve/.venvs/vllm-xpu/bin/python3 | cut -d' ' -f1)" == "$expected_python" ]] || fail "build Python changed"
  read -r python_version torch_version < <(/home/steve/.venvs/vllm-xpu/bin/python3 - <<'PY'
import sys
import torch
print(sys.version.split()[0], torch.__version__)
PY
)
  [[ "$python_version" == 3.12.13 && "$torch_version" == 2.11.0+xpu ]] || fail "Python or Torch version changed"
  (cd "$old_stage" && sha256sum -c "$old_manifest") >/dev/null || fail "old serving stage failed its manifest"
}

cache_has() {
  grep -Fxq "$1" "${build_dir}/CMakeCache.txt" || fail "generated CMake cache lacks: $1"
}

[[ $# == 0 ]] || fail "this frozen build takes no arguments"
exec 9>/tmp/q38-xpu-kernel-build.lock
flock -n 9 || fail "another XPU-kernel build owns the exclusive lock"
! ps -eo comm= | grep -Eq '^(cmake|ninja|icx|icpx)$' || fail "another native build process is active"
read -r mount_source mount_fstype mount_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/fast-ai)
[[ "$mount_source" == /dev/nvme0n1p2 && "$mount_fstype" == ext4 && "$mount_target" == / ]] || fail "local build root is not the expected NVMe/ext4 mount"
read -r evidence_source evidence_fstype evidence_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
[[ "$evidence_source" == /dev/sda2 && "$evidence_fstype" == fuseblk && "$evidence_target" == /mnt/usb-models ]] || fail "accepted stage is not on the authenticated external drive"
[[ -r "$old_stage" && -x "$old_stage" ]] || fail "accepted stage is not readable"
(( $(df --output=avail -B1 /mnt/fast-ai | tail -1) >= 161061273600 )) || fail "local NVMe has less than 150 GiB free"
(( $(awk '/MemAvailable/ {print $2 * 1024}' /proc/meminfo) >= 107374182400 )) || fail "host has less than 100 GiB available memory"
(( $(awk '/SwapFree/ {print $2 * 1024}' /proc/meminfo) >= 7516192768 )) || fail "host has less than 7 GiB free swap"
active_model_processes=$(/usr/bin/python3 - <<'PY'
from pathlib import Path

markers = (b"vllm serve", b"VLLM::EngineCore", b"supervise-tp4")
hits = []
for entry in Path("/proc").iterdir():
    if not entry.name.isdigit():
        continue
    try:
        command = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        continue
    if any(marker in command for marker in markers):
        hits.append(entry.name)
print(" ".join(sorted(hits, key=int)))
PY
)
[[ -z "$active_model_processes" ]] || fail "a model server or supervisor is active: $active_model_processes"
check_source_closure
[[ "$(awk 'END {print NR}' "$old_manifest")" == 18 ]] || fail "old manifest is not the expected 18-file inventory"

for path in "$build_dir" "$install_prefix" "$stage_root" "$evidence" "$fetchcontent"; do
  [[ ! -e "$path" ]] || fail "output already exists: $path"
done
[[ "${Q38_GROUPED_STAGE_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validation-only selector"
if [[ "${Q38_GROUPED_STAGE_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: frozen grouped-serving build preflight\n'
  exit 0
fi

mkdir -p "$(dirname "$build_dir")" "$evidence"
printf '%s\n' "$expected_kernels" >"${evidence}/kernel-head.txt"
printf '%s\n' "$expected_kernel_chain" >"${evidence}/kernel-chain.txt"

set +e
BUILD_DIR="$build_dir" \
INSTALL_PREFIX="$install_prefix" \
FETCHCONTENT_DIR="$fetchcontent" \
ONEDNN_SOURCE="$onednn" \
CUTLASS_SOURCE="$cutlass" \
AOT_DEVICES=bmg-g21-a0 \
JOBS=2 \
GDN_KERNELS=ON \
MOE_KERNELS=ON \
"$builder" 2>&1 | tee "${evidence}/build.log"
pipeline_rc=("${PIPESTATUS[@]}")
set -e
build_rc=${pipeline_rc[0]}
tee_rc=${pipeline_rc[1]}
printf '%s\n' "$build_rc" >"${evidence}/build.exit-code"
printf '%s\n' "$tee_rc" >"${evidence}/tee.exit-code"
[[ "$build_rc" == 0 ]] || fail "native build failed; evidence preserved at $evidence"
[[ "$tee_rc" == 0 ]] || fail "build-log capture failed; evidence preserved at $evidence"

check_source_closure
cache_has 'CMAKE_BUILD_TYPE:STRING=Release'
cache_has 'CMAKE_GENERATOR:INTERNAL=Ninja'
cache_has 'CMAKE_COMMAND:INTERNAL=/home/steve/.local/share/uv/tools/cmake/lib/python3.12/site-packages/cmake/data/bin/cmake'
cache_has 'CMAKE_HOME_DIRECTORY:INTERNAL=/home/steve/src/vllm-xpu-kernels'
cache_has 'CMAKE_TOOLCHAIN_FILE:FILEPATH=/home/steve/src/vllm-xpu-kernels/cmake/toolchain.cmake'
cache_has 'CMAKE_MAKE_PROGRAM:FILEPATH=/home/steve/.local/bin/ninja'
cache_has 'SYCL_COMPILER:FILEPATH=/opt/intel/oneapi/compiler/2025.3/bin/icx'
cache_has 'Torch_DIR:PATH=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/share/cmake/Torch'
cache_has 'FETCHCONTENT_BASE_DIR:PATH=/mnt/fast-ai/qwen38-build/deps-xpu-serving-eeee7d6-a1'
cache_has 'FETCHCONTENT_SOURCE_DIR_ONEDNN:UNINITIALIZED=/home/steve/src/vllm-xpu-kernels/.deps/onednn-src'
cache_has 'VLLM_PYTHON_EXECUTABLE:UNINITIALIZED=/home/steve/.venvs/vllm-xpu/bin/python3'
cache_has 'BUILD_SYCL_TLA_KERNELS:BOOL=ON'
cache_has 'VLLM_XPU_ENABLE_XE2:BOOL=ON'
cache_has 'VLLM_XPU_ENABLE_XE_DEFAULT:BOOL=OFF'
cache_has 'BASIC_KERNELS_ENABLED:BOOL=OFF'
cache_has 'FA2_KERNELS_ENABLED:BOOL=OFF'
cache_has 'MOE_KERNELS_ENABLED:BOOL=ON'
cache_has 'GDN_KERNELS_ENABLED:BOOL=ON'
cache_has 'MQA_LOGITS_KERNELS_ENABLED:BOOL=OFF'
cache_has 'XPU_SPECIFIC_KERNELS_ENABLED:BOOL=ON'
cache_has 'XPUMEM_ALLOCATOR_ENABLED:BOOL=OFF'
cache_has 'DPCPP_SYCL_TARGET:STRING=intel_gpu_bmg_g21'
grep -Fq -- '-device bmg-g21-a0' "${evidence}/build.log" || fail "build log lacks the frozen B70 AOT target"
grep -Fq 'The VLLM_CUTLASS_SRC_DIR is set, using /home/steve/src/vllm-xpu-kernels/.deps/cutlass-sycl-src for compilation' "${evidence}/build.log" || fail "build did not use the pinned SYCL-TLA source"
! grep -Fq "${kernels}/third_party/" "${build_dir}/compile_commands.json" || fail "untracked root third_party entered compilation"

candidate_xpu="${install_prefix}/vllm_xpu_kernels/_xpu_C.abi3.so"
candidate_gdn="${install_prefix}/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so"
candidate_grouped="${build_dir}/libgrouped_gemm_xe_2.so"
for path in "$candidate_xpu" "$candidate_gdn" "$candidate_grouped"; do
  [[ -f "$path" && ! -L "$path" ]] || fail "candidate output is absent or not a regular file: $path"
done

mkdir -p "$stage"
while read -r _ relative; do
  install -D -m "$(case "$relative" in *.so) printf 0755;; *) printf 0644;; esac)" \
    "${old_stage}/${relative}" "${stage}/${relative}"
done <"$old_manifest"
install -m 0755 "$candidate_xpu" "${stage}/_xpu_C.abi3.so"
install -m 0755 "$candidate_gdn" "${stage}/libgdn_attn_kernels_xe_2.so"
install -m 0755 "$candidate_grouped" "${stage}/libgrouped_gemm_xe_2.so"

patchelf --set-rpath '$ORIGIN' "${stage}/_xpu_C.abi3.so"
patchelf --set-rpath '$ORIGIN' "${stage}/libgdn_attn_kernels_xe_2.so"
patchelf --set-rpath '$ORIGIN' "${stage}/libgrouped_gemm_xe_2.so"

(cd "$stage" && find . -type f \( -name '*.py' -o -name '*.so' \) -printf '%P\n' | LC_ALL=C sort) >"${evidence}/stage-files.txt"
cut -d' ' -f3- "$old_manifest" >"${evidence}/expected-stage-files.txt"
cmp -s "${evidence}/expected-stage-files.txt" "${evidence}/stage-files.txt" || fail "candidate stage inventory differs"
(cd "$stage" && sha256sum $(cat "${evidence}/stage-files.txt")) >"${evidence}/runtime-stage.sha256"

for relative in $(cat "${evidence}/stage-files.txt"); do
  case "$relative" in
    _xpu_C.abi3.so|libgdn_attn_kernels_xe_2.so|libgrouped_gemm_xe_2.so) ;;
    *)
      old_hash=$(awk -v file="$relative" '$2 == file {print $1}' "$old_manifest")
      new_hash=$(awk -v file="$relative" '$2 == file {print $1}' "${evidence}/runtime-stage.sha256")
      [[ -n "$old_hash" && "$new_hash" == "$old_hash" ]] || fail "untreated runtime file changed: $relative"
      ;;
  esac
done

readelf -d "${stage}/_xpu_C.abi3.so" >"${evidence}/xpu-dynamic.txt"
grep -Fq 'Shared library: [libgdn_attn_kernels_xe_2.so]' "${evidence}/xpu-dynamic.txt" || fail "candidate extension lacks GDN dependency"
grep -Fq 'Shared library: [libgrouped_gemm_xe_2.so]' "${evidence}/xpu-dynamic.txt" || fail "candidate extension lacks grouped dependency"
grep -Fq 'Library runpath: [$ORIGIN]' "${evidence}/xpu-dynamic.txt" || fail "candidate extension lacks isolated runpath"

loader_path="${stage}:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib"
LD_LIBRARY_PATH="$loader_path" ldd "${stage}/_xpu_C.abi3.so" >"${evidence}/xpu-ldd.txt"
! grep -Fq 'not found' "${evidence}/xpu-ldd.txt" || fail "candidate extension has an unresolved dependency"
grep -Fq "libgdn_attn_kernels_xe_2.so => ${stage}/libgdn_attn_kernels_xe_2.so" "${evidence}/xpu-ldd.txt" || fail "GDN did not resolve inside candidate stage"
grep -Fq "libgrouped_gemm_xe_2.so => ${stage}/libgrouped_gemm_xe_2.so" "${evidence}/xpu-ldd.txt" || fail "grouped library did not resolve inside candidate stage"
grep -Fq 'libsycl.so.8 => /home/steve/.venvs/vllm-xpu/lib/libsycl.so.8' "${evidence}/xpu-ldd.txt" || fail "candidate did not resolve the frozen SYCL 8 runtime"
[[ "$(sha256sum /home/steve/.venvs/vllm-xpu/lib/libsycl.so.8 | cut -d' ' -f1)" == "$expected_sycl" ]] || fail "SYCL 8 runtime changed"

check_source_closure

sha256sum "$0" "$builder" "$old_manifest" "$topk_patch" "$grouped_patch" \
  /usr/bin/patchelf /home/steve/.local/bin/cmake /home/steve/.local/bin/ninja \
  /opt/intel/oneapi/compiler/2025.3/bin/icx /home/steve/.venvs/vllm-xpu/bin/python3 \
  /home/steve/.venvs/vllm-xpu/lib/libsycl.so.8 \
  "$build_dir/CMakeCache.txt" "$build_dir/compile_commands.json" \
  "${evidence}/build.log" "${evidence}/xpu-dynamic.txt" \
  "${evidence}/xpu-ldd.txt" "${evidence}/runtime-stage.sha256" \
  >"${evidence}/build-evidence.sha256"

printf 'PASS: built isolated grouped+GDN serving stage at %s\n' "$stage_root"
printf 'MANIFEST: %s\n' "${evidence}/runtime-stage.sha256"
