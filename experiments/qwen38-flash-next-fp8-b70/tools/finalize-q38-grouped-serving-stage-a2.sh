#!/usr/bin/env bash
set -Eeuo pipefail

repo=/home/steve/llm-optimizations
kernels=/home/steve/src/vllm-xpu-kernels
vllm=/home/steve/src/vllm-current-main
old_stage=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70/vllm_xpu_kernels
old_manifest="${repo}/experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256"
a1_driver="${repo}/experiments/qwen38-flash-next-fp8-b70/tools/build-q38-grouped-serving-stage-a1.sh"
builder="${repo}/scripts/build-vllm-xpu-kernels-xpu-c-only.sh"
a1_build=/mnt/fast-ai/qwen38-build/build-xpu-serving-eeee7d6-a1
a1_install=/mnt/fast-ai/qwen38-build/install-xpu-serving-eeee7d6-a1
a1_evidence=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a1-evidence
a1_stage=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a1
stage_root=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2
stage="${stage_root}/vllm_xpu_kernels"
evidence=/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2-evidence

cmake_command=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/cmake/data/bin/cmake
ninja=/home/steve/.venvs/vllm-xpu/bin/ninja
patchelf=/usr/bin/patchelf
sycl=/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8
candidate_xpu="${a1_install}/vllm_xpu_kernels/_xpu_C.abi3.so"
candidate_gdn="${a1_install}/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so"
candidate_grouped="${a1_build}/libgrouped_gemm_xe_2.so"

expected_a1_driver=b5c29a50c3e6e3b737312fcb2392df9e5b252ef38cd038674c1bf11d4c3bd336
expected_builder=5cbdadc200626ed9da03b6aa4808a59ee848348c671ce76d4d7ada4a37ca464f
expected_old_manifest=9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b
expected_vllm=797769b34b6db5c934609b75dc04cc61ec66e5f9
expected_kernels=eeee7d671abfa964626baa18da2174bb92cac80a
expected_kernel_chain=$'eeee7d671abfa964626baa18da2174bb92cac80a\n042c6e877b667f03087091ce3ab58b80903afc20\na6ee94fd8fadb97dc033921f1019ef18f14d5dd0\n359466a262489bdf4e1774e3572202dc82a00718\nad25aa9f69a2171612b9c6b83dfa82c69559f9e4'
expected_build_log=6bcaad7fc092af76468c82ba881a62f3e7e0a9da15b186a7a032e7e99b6871c3
expected_build_exit=9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa
expected_kernel_head_receipt=70899a5726e7677d64bf5b2a988804fdff8f071ef917db8c65ba8995c920c294
expected_kernel_chain_receipt=45701dec2b756219edeac3305012bf30d84e0863525dc4afc508896ab4018bf4
expected_cache=94f11621328ba1cc2e46c81c0f6ce15e2bce24695c861375e600b80ac394a698
expected_compile_commands=04090a0c4a969cd83eedcc2db77c4a108ca241af2cb1cd44c29b54f9e3be5818
expected_candidate_xpu=8d6d41a2259b4d4eda53edd9524d113d9190ae1b093a150fd79aa72a5c28dd76
expected_candidate_gdn=249cd714ca6976346b40a31d260c66149c48e1fe5e7c15df9277db6b155f2ed0
expected_candidate_grouped=ef81dd90441346671220e55f57e8b1f682394d24aeb70c79c444003e8b40ed64
expected_cmake=2cb2b2ed8a79eb5612bd611d010c882bf467feb51ad69dac288a245519080408
expected_ninja=696f9628a79d9ce50314cf9556d7cd1a1d1ec52b8fd52828f6f9db1719565b67
expected_patchelf=35fc95654387035338a74bb8cf62fde3712ec83dd8ca30a768deb714d07f063a
expected_sycl=0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

hash_is() {
  local path=$1 expected=$2 label=$3
  [[ -f "$path" && ! -L "$path" ]] || fail "$label is absent or not a regular file"
  [[ "$(sha256sum "$path" | cut -d' ' -f1)" == "$expected" ]] || fail "$label digest drifted"
}

cache_has() {
  grep -Fxq "$1" "${a1_build}/CMakeCache.txt" || fail "A1 CMake cache lacks: $1"
}

check_sources() {
  hash_is "$a1_driver" "$expected_a1_driver" "A1 build driver"
  hash_is "$builder" "$expected_builder" "native builder"
  hash_is "$old_manifest" "$expected_old_manifest" "accepted-stage manifest"
  hash_is "$cmake_command" "$expected_cmake" "A1 CMake executable"
  hash_is "$ninja" "$expected_ninja" "A1 Ninja executable"
  hash_is "$patchelf" "$expected_patchelf" "patchelf"
  hash_is "$sycl" "$expected_sycl" "SYCL runtime"
  [[ "$(git -C "$vllm" rev-parse HEAD)" == "$expected_vllm" ]] || fail "vLLM head changed"
  [[ -z "$(git -C "$vllm" status --porcelain --untracked-files=no)" ]] || fail "vLLM has tracked changes"
  [[ "$(git -C "$kernels" rev-parse HEAD)" == "$expected_kernels" ]] || fail "kernel head changed"
  [[ "$(git -C "$kernels" rev-list --max-count=5 HEAD)" == "$expected_kernel_chain" ]] || fail "kernel source chain changed"
  [[ -z "$(git -C "$kernels" status --porcelain --untracked-files=no)" ]] || fail "kernel source has tracked changes"
  [[ "$(git -C "$kernels" status --porcelain)" == '?? third_party/' ]] || fail "unexpected untracked kernel-source content"
  (cd "$old_stage" && sha256sum -c "$old_manifest") >/dev/null || fail "accepted stage failed its manifest"
}

check_a1_build() {
  [[ ! -e "$a1_stage" ]] || fail "A1 stage unexpectedly exists"
  hash_is "${a1_evidence}/build.log" "$expected_build_log" "A1 build log"
  hash_is "${a1_evidence}/build.exit-code" "$expected_build_exit" "A1 build exit receipt"
  hash_is "${a1_evidence}/tee.exit-code" "$expected_build_exit" "A1 tee exit receipt"
  hash_is "${a1_evidence}/kernel-head.txt" "$expected_kernel_head_receipt" "A1 kernel-head receipt"
  hash_is "${a1_evidence}/kernel-chain.txt" "$expected_kernel_chain_receipt" "A1 kernel-chain receipt"
  hash_is "${a1_build}/CMakeCache.txt" "$expected_cache" "A1 CMake cache"
  hash_is "${a1_build}/compile_commands.json" "$expected_compile_commands" "A1 compile database"
  hash_is "$candidate_xpu" "$expected_candidate_xpu" "A1 native extension"
  hash_is "$candidate_gdn" "$expected_candidate_gdn" "A1 GDN library"
  hash_is "$candidate_grouped" "$expected_candidate_grouped" "A1 grouped library"
  [[ "$(cat "${a1_evidence}/build.exit-code")" == 0 ]] || fail "A1 native build did not pass"
  [[ "$(cat "${a1_evidence}/tee.exit-code")" == 0 ]] || fail "A1 log capture did not pass"
  [[ "$(grep -Ec '^\[[0-9]+/711\] ' "${a1_evidence}/build.log")" == 711 ]] || fail "A1 build log lacks the exact 711-step sequence"
  grep -Fq '[711/711] Linking CXX shared module _xpu_C.abi3.so' "${a1_evidence}/build.log" || fail "A1 final native link receipt is absent"
  grep -Fxq 'Build succeeded.' "${a1_evidence}/build.log" || fail "A1 success receipt is absent"
  grep -Fq -- '-device bmg-g21-a0' "${a1_evidence}/build.log" || fail "A1 log lacks the B70 AOT target"
  grep -Fq 'The VLLM_CUTLASS_SRC_DIR is set, using /home/steve/src/vllm-xpu-kernels/.deps/cutlass-sycl-src for compilation' "${a1_evidence}/build.log" || fail "A1 log lacks the pinned SYCL-TLA source"

  cache_has 'CMAKE_BUILD_TYPE:STRING=Release'
  cache_has 'CMAKE_GENERATOR:INTERNAL=Ninja'
  cache_has 'CMAKE_COMMAND:INTERNAL=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/cmake/data/bin/cmake'
  cache_has 'CMAKE_HOME_DIRECTORY:INTERNAL=/home/steve/src/vllm-xpu-kernels'
  cache_has 'CMAKE_TOOLCHAIN_FILE:FILEPATH=/home/steve/src/vllm-xpu-kernels/cmake/toolchain.cmake'
  cache_has 'CMAKE_MAKE_PROGRAM:FILEPATH=/home/steve/.venvs/vllm-xpu/bin/ninja'
  cache_has 'SYCL_COMPILER:FILEPATH=/opt/intel/oneapi/compiler/2025.3/bin/icx'
  cache_has 'Torch_DIR:PATH=/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/share/cmake/Torch'
  cache_has 'FETCHCONTENT_BASE_DIR:PATH=/mnt/fast-ai/qwen38-build/deps-xpu-serving-eeee7d6-a1'
  cache_has 'FETCHCONTENT_SOURCE_DIR_ONEDNN:PATH=/home/steve/src/vllm-xpu-kernels/.deps/onednn-src'
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
  ! grep -Fq "${kernels}/third_party/" "${a1_build}/compile_commands.json" || fail "untracked root third_party entered A1 compilation"
}

check_mounts_and_processes() {
  local mount_source mount_fstype mount_target active
  read -r mount_source mount_fstype mount_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/fast-ai)
  [[ "$mount_source" == /dev/nvme0n1p2 && "$mount_fstype" == ext4 && "$mount_target" == / ]] || fail "local build root is not authenticated NVMe/ext4"
  read -r mount_source mount_fstype mount_target < <(findmnt -nro SOURCE,FSTYPE,TARGET --target /mnt/usb-models)
  [[ "$mount_source" == /dev/sda2 && "$mount_fstype" == fuseblk && "$mount_target" == /mnt/usb-models ]] || fail "accepted stage drive is not authenticated"
  (( $(df --output=avail -B1 /mnt/fast-ai | tail -1) >= 1073741824 )) || fail "local NVMe has less than 1 GiB free"
  active=$(/usr/bin/python3 - <<'PY'
from pathlib import Path

markers = (
    b"build-vllm-xpu-kernels",
    b"build-q38-grouped-serving-stage",
    b"vllm serve",
    b"VLLM::EngineCore",
    b"supervise-tp4",
)
own = str(Path("/proc/self").resolve()).rsplit("/", 1)[-1]
hits = []
for entry in Path("/proc").iterdir():
    if not entry.name.isdigit() or entry.name == own:
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
  [[ -z "$active" ]] || fail "a native build, model server, or supervisor is active: $active"
}

[[ $# == 0 ]] || fail "this frozen finalizer takes no arguments"
[[ "${Q38_GROUPED_STAGE_A2_VALIDATE_ONLY:-0}" =~ ^[01]$ ]] || fail "invalid validation-only selector"
exec 9>/tmp/q38-grouped-serving-stage-a2-finalize.lock
flock -n 9 || fail "another A2 finalizer owns the exclusive lock"
check_mounts_and_processes
check_sources
check_a1_build
for path in "$stage_root" "$evidence"; do
  [[ ! -e "$path" ]] || fail "A2 output already exists: $path"
done
if [[ "${Q38_GROUPED_STAGE_A2_VALIDATE_ONLY:-0}" == 1 ]]; then
  printf 'PASS: A1 build closure permits assembly-only A2 finalization\n'
  exit 0
fi

mkdir -p "$stage" "$evidence"
printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id)" >"${evidence}/boot-id.txt"
printf '%s\n' '0' >"${evidence}/a1-build-exit-code.txt"
printf '%s\n' '0' >"${evidence}/a1-tee-exit-code.txt"
printf '%s\n' 'A1 native build passed; A1 finalization stopped on incorrect CMake/cache-type assertions.' >"${evidence}/a1-classification.txt"

while read -r _ relative; do
  install -D -m "$(case "$relative" in *.so) printf 0755;; *) printf 0644;; esac)" \
    "${old_stage}/${relative}" "${stage}/${relative}"
done <"$old_manifest"
install -m 0755 "$candidate_xpu" "${stage}/_xpu_C.abi3.so"
install -m 0755 "$candidate_gdn" "${stage}/libgdn_attn_kernels_xe_2.so"
install -m 0755 "$candidate_grouped" "${stage}/libgrouped_gemm_xe_2.so"

"$patchelf" --set-rpath '$ORIGIN' "${stage}/_xpu_C.abi3.so"
"$patchelf" --set-rpath '$ORIGIN' "${stage}/libgdn_attn_kernels_xe_2.so"
"$patchelf" --set-rpath '$ORIGIN' "${stage}/libgrouped_gemm_xe_2.so"

(cd "$stage" && find . -type f \( -name '*.py' -o -name '*.so' \) -printf '%P\n' | LC_ALL=C sort) >"${evidence}/stage-files.txt"
cut -d' ' -f3- "$old_manifest" >"${evidence}/expected-stage-files.txt"
cmp -s "${evidence}/expected-stage-files.txt" "${evidence}/stage-files.txt" || fail "A2 stage inventory differs"
(cd "$stage" && xargs -r sha256sum <"${evidence}/stage-files.txt") >"${evidence}/runtime-stage.sha256"
[[ "$(awk 'END {print NR}' "${evidence}/runtime-stage.sha256")" == 18 ]] || fail "A2 stage manifest is not 18 entries"

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
grep -Fq 'Shared library: [libgdn_attn_kernels_xe_2.so]' "${evidence}/xpu-dynamic.txt" || fail "A2 extension lacks GDN dependency"
grep -Fq 'Shared library: [libgrouped_gemm_xe_2.so]' "${evidence}/xpu-dynamic.txt" || fail "A2 extension lacks grouped dependency"
grep -Fq 'Library runpath: [$ORIGIN]' "${evidence}/xpu-dynamic.txt" || fail "A2 extension lacks isolated runpath"

loader_path="${stage}:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib"
LD_LIBRARY_PATH="$loader_path" ldd "${stage}/_xpu_C.abi3.so" >"${evidence}/xpu-ldd.txt"
! grep -Fq 'not found' "${evidence}/xpu-ldd.txt" || fail "A2 extension has an unresolved dependency"
grep -Fq "libgdn_attn_kernels_xe_2.so => ${stage}/libgdn_attn_kernels_xe_2.so" "${evidence}/xpu-ldd.txt" || fail "GDN did not resolve inside A2"
grep -Fq "libgrouped_gemm_xe_2.so => ${stage}/libgrouped_gemm_xe_2.so" "${evidence}/xpu-ldd.txt" || fail "grouped library did not resolve inside A2"
grep -Fq 'libsycl.so.8 => /home/steve/.venvs/vllm-xpu/lib/libsycl.so.8' "${evidence}/xpu-ldd.txt" || fail "A2 did not resolve the frozen SYCL runtime"

check_mounts_and_processes
check_sources
check_a1_build
(cd "$stage" && sha256sum -c "${evidence}/runtime-stage.sha256") >/dev/null || fail "A2 stage failed its closing manifest"

driver_relative=${0#"${repo}/"}
(
  cd "$repo"
  sha256sum "$driver_relative" \
    "${a1_driver#"${repo}/"}" "${builder#"${repo}/"}" \
    "${old_manifest#"${repo}/"}" \
    "$cmake_command" "$ninja" "$patchelf" "$sycl" \
    "${a1_evidence}/build.log" "${a1_evidence}/build.exit-code" \
    "${a1_evidence}/tee.exit-code" "${a1_evidence}/kernel-head.txt" \
    "${a1_evidence}/kernel-chain.txt" "${a1_build}/CMakeCache.txt" \
    "${a1_build}/compile_commands.json" "$candidate_xpu" \
    "$candidate_gdn" "$candidate_grouped" \
    "${evidence}/boot-id.txt" "${evidence}/a1-build-exit-code.txt" \
    "${evidence}/a1-tee-exit-code.txt" "${evidence}/a1-classification.txt" \
    "${evidence}/stage-files.txt" "${evidence}/expected-stage-files.txt" \
    "${evidence}/runtime-stage.sha256" "${evidence}/xpu-dynamic.txt" \
    "${evidence}/xpu-ldd.txt"
) >"${evidence}/finalizer-evidence.sha256"

printf 'PASS: finalized isolated grouped+GDN serving stage at %s\n' "$stage_root"
printf 'MANIFEST: %s\n' "${evidence}/runtime-stage.sha256"
