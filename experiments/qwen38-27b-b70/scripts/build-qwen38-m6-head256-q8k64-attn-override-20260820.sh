#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
helper_path=$(realpath -e -- "${BASH_SOURCE[0]}")
lane_dir=$(cd -- "$script_dir/.." && pwd)
repo_root=$(git -C "$lane_dir" rev-parse --show-toplevel)
source_tree=${SOURCE_TREE:-/home/steve/src/vllm-xpu-kernels}
base_stage=${BASE_STAGE:-/home/steve/staged-xpu-commitfix-graphfa-composite-20260820}
python_bin=${PYTHON_BIN:-/home/steve/.venvs/vllm-xpu/bin/python}
compiler_root=${INTEL_COMPILER_ROOT:-/opt/intel/oneapi/compiler/2025.3}
candidate_patch="$lane_dir/patches/vllm-xpu-kernels-qwen38-m6-head256-q8k64-chunk-prefill-20260820.patch"
graph_dir="$repo_root/experiments/qwen27_graphsafe_flash_attention"
local_accessor_patch="$graph_dir/qwen27-chunk-prefill-local-accessor.patch"
chunk_config="$graph_dir/qwen38-head256-chunk.conf"
paged_config="$graph_dir/qwen38-head256-paged.conf"
cutlass_tree="$source_tree/.deps/cutlass-sycl-src"
qualifier="$lane_dir/scripts/qwen38_mtp5_m6_fa_operator.py"
export PYTHONDONTWRITEBYTECODE=1

expected_source_head=2dd55f380df753a10a88fcd9e96192561066e713
expected_fmha_sha=427462029379cfaf2e75c9222094bebdadca6c272e497ca0dda42617097a9784
expected_chunk_prefill_sha=f43ccc42c557b38c8cac4ac7708b7db4f8f6f11e304fb6d69602d8848ef2a83b
expected_fmha_utils_sha=a4d56fa0dd6cca86493930563a71621e1c472d28026d48faf11a421796455c10
expected_flash_api_sha=32227dea9a36199a4d05dd5ffcce33d0998281a192b8223ad9bc4d231bb042f3
expected_cutlass_head=cd763790ad2f74d7294435ecf77682bac0062c3a
expected_top_cmake_sha=dea8c149ef60a38b819c2689f5631de2bfee3cc48db79434ec5386db0fd40339
expected_utils_cmake_sha=c4efaf8edb72265ebea7b0c51a67ac482a86d2783d0e1bbc7fad1bd4c8f1000a
expected_attn_cmake_sha=fe7c137f5a50f1eb80f469f02ea8c661544084e1e4b4cf43f929ec2fc5c787cf
expected_candidate_patch_sha=06467757a7482ad0e3225c9a59ce3d2de144453a608016737c7a24dbe48b5fc1
expected_local_accessor_patch_sha=1f1a016bbf9cd4a71a47657846143913d879424fce73a9f669f982bcdaad165e
expected_chunk_config_sha=6b9104b93b1a24135a8d4ab12bc10c71a4cdae481be9959586eff8994bb224cf
expected_paged_config_sha=0f119bf11e551dc2aba205dcde593f6e841c3e501deb718cf5ba59918d2c52c2
expected_extension_sha=33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739
expected_wrapper_sha=869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480
expected_stock_sha=3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289
expected_incumbent_sha=604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c
aot_devices=pvc,bmg,bmg-g21-a0,bmg-g31-a0

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

verify_sha() {
  local path=$1
  local expected=$2
  local actual
  [[ -f $path ]] || die "missing required file: $path"
  actual=$(sha256sum -- "$path" | awk '{print $1}')
  [[ $actual == "$expected" ]] ||
    die "SHA-256 mismatch for $path (expected $expected, got $actual)"
}

usage() {
  printf 'usage: %s --validate-only\n' "$0" >&2
  printf '       WORK_ROOT=/new/absolute/path %s --build\n' "$0" >&2
}

[[ $# -eq 1 ]] || { usage; exit 2; }
mode=$1
[[ $mode == --validate-only || $mode == --build ]] || { usage; exit 2; }

command -v git >/dev/null || die 'git is required'
command -v sha256sum >/dev/null || die 'sha256sum is required'
command -v readelf >/dev/null || die 'readelf is required'
command -v nm >/dev/null || die 'nm is required'
command -v strings >/dev/null || die 'strings is required'
command -v realpath >/dev/null || die 'realpath is required'
command -v tar >/dev/null || die 'tar is required'
[[ -x $python_bin ]] || die "Python is not executable: $python_bin"
[[ -x $compiler_root/bin/icpx ]] ||
  die "oneAPI icpx is not executable: $compiler_root/bin/icpx"

[[ $(git -C "$source_tree" rev-parse HEAD) == "$expected_source_head" ]] ||
  die "source HEAD is not $expected_source_head"
git -C "$source_tree" diff --quiet -- csrc/xpu/attn/xe_2/fmha_xe2.cpp ||
  die 'source fmha_xe2.cpp has a tracked worktree delta'
git -C "$source_tree" diff --cached --quiet -- csrc/xpu/attn/xe_2/fmha_xe2.cpp ||
  die 'source fmha_xe2.cpp has a staged delta'
[[ ! -e $source_tree/csrc/xpu/attn/xe_2/m6_head256_chunk_prefill.cpp ]] ||
  die 'candidate source already exists in the live source tree'

verify_sha "$source_tree/csrc/xpu/attn/xe_2/fmha_xe2.cpp" "$expected_fmha_sha"
verify_sha "$source_tree/csrc/xpu/attn/xe_2/chunk_prefill.hpp" "$expected_chunk_prefill_sha"
verify_sha "$source_tree/csrc/xpu/attn/xe_2/fmha_utils.hpp" "$expected_fmha_utils_sha"
verify_sha "$source_tree/csrc/flash_attn/flash_api.cpp" "$expected_flash_api_sha"
verify_sha "$source_tree/CMakeLists.txt" "$expected_top_cmake_sha"
verify_sha "$source_tree/cmake/utils.cmake" "$expected_utils_cmake_sha"
verify_sha "$source_tree/csrc/xpu/attn/xe_2/CMakeLists.txt" "$expected_attn_cmake_sha"
[[ $(git -C "$cutlass_tree" rev-parse HEAD) == "$expected_cutlass_head" ]] ||
  die "CUTLASS-SYCL HEAD is not $expected_cutlass_head"
git -C "$cutlass_tree" diff --quiet || die 'CUTLASS-SYCL worktree is dirty'
git -C "$cutlass_tree" diff --cached --quiet ||
  die 'CUTLASS-SYCL index is dirty'
git -C "$source_tree" archive "$expected_source_head" -- \
  CMakeLists.txt csrc/xpu/attn/xe_2/fmha_xe2.cpp |
  tar -tf - >/dev/null
git -C "$cutlass_tree" archive "$expected_cutlass_head" -- \
  include/cute/tensor.hpp |
  tar -tf - >/dev/null
verify_sha "$candidate_patch" "$expected_candidate_patch_sha"
verify_sha "$local_accessor_patch" "$expected_local_accessor_patch_sha"
verify_sha "$chunk_config" "$expected_chunk_config_sha"
verify_sha "$paged_config" "$expected_paged_config_sha"
[[ -f $qualifier ]] || die "operator qualifier is absent: $qualifier"
grep -Fq 'SCHEMA_STAGE = "qwen38-mtp5-m6-fa-stage-v1"' "$qualifier" ||
  die 'operator qualifier stage schema differs'
grep -Fq 'BUILD_INPUTS_BASENAME = "qwen38-m6-head256-q8k64-build-inputs.sha256"' \
  "$qualifier" || die 'operator qualifier build-input artifact contract differs'

git -C "$source_tree" apply --unidiff-zero --check "$candidate_patch"
git -C "$source_tree" apply --check "$local_accessor_patch"

apply_check_root=$(mktemp -d /tmp/qwen38-m6-q8k64-apply.XXXXXX)
trap 'rm -rf -- "$apply_check_root"' EXIT
mkdir -p "$apply_check_root/csrc/xpu/attn/xe_2"
cp "$source_tree/csrc/xpu/attn/xe_2/fmha_xe2.cpp" \
  "$source_tree/csrc/xpu/attn/xe_2/chunk_prefill.hpp" \
  "$apply_check_root/csrc/xpu/attn/xe_2/"
(
  cd "$apply_check_root"
  git apply "$local_accessor_patch"
  git apply --unidiff-zero "$candidate_patch"
  git apply --unidiff-zero --reverse --check "$candidate_patch"
  git apply --unidiff-zero --reverse "$candidate_patch"
  git apply --reverse --check "$local_accessor_patch"
)
rm -rf -- "$apply_check_root"
trap - EXIT

verify_sha "$base_stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
  "$expected_extension_sha"
verify_sha "$base_stage/vllm_xpu_kernels/flash_attn_interface.py" \
  "$expected_wrapper_sha"
verify_sha "$base_stage/vllm_xpu_kernels/libattn_stock.so" \
  "$expected_stock_sha"
verify_sha "$base_stage/vllm_xpu_kernels/libattn_kernels_xe_2.so" \
  "$expected_incumbent_sha"
readelf -d "$base_stage/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" |
  grep -F 'Shared library: [libattn_kernels_xe_2.so]' >/dev/null ||
  die '_vllm_fa2_C does not require libattn_kernels_xe_2.so'
readelf -d "$base_stage/vllm_xpu_kernels/libattn_stock.so" |
  grep -F 'Library soname: [libattn_stock.so]' >/dev/null ||
  die 'stock attention DSO has the wrong SONAME'

if [[ $mode == --validate-only ]]; then
  printf 'PASS: pinned source, patch, configs, and incumbent runtime boundary validate.\n'
  exit 0
fi

[[ -n ${WORK_ROOT:-} ]] || die 'WORK_ROOT is required for --build'
[[ $WORK_ROOT == /* ]] || die 'WORK_ROOT must be an absolute path'
[[ $WORK_ROOT != */ ]] || die 'WORK_ROOT must not have a trailing slash'
[[ ! -e $WORK_ROOT ]] || die 'WORK_ROOT must not already exist'
work_parent=$(dirname -- "$WORK_ROOT")
work_leaf=$(basename -- "$WORK_ROOT")
[[ -d $work_parent ]] || die "WORK_ROOT parent is absent: $work_parent"
canonical_parent=$(realpath -e -- "$work_parent")
[[ $WORK_ROOT == "$canonical_parent/$work_leaf" ]] ||
  die 'WORK_ROOT must already be canonical (no symlinked parent components)'
case "$WORK_ROOT" in
  /|/home|/home/steve|"$repo_root"|"$source_tree"|"$base_stage")
    die 'WORK_ROOT is too broad or aliases a protected tree'
    ;;
esac
case "$WORK_ROOT/" in
  "$repo_root/"*|"$source_tree/"*|"$base_stage/"*)
    die 'WORK_ROOT must be outside repo, source, and incumbent stage trees'
    ;;
esac

command -v cmake >/dev/null || die 'cmake is required'
command -v ninja >/dev/null || die 'ninja is required'
command -v rsync >/dev/null || die 'rsync is required'

stage="$WORK_ROOT/source"
build="$WORK_ROOT/build"
runtime="$WORK_ROOT/runtime"
artifact="$WORK_ROOT/libattn_kernels_xe_2.so"
mkdir -p -- "$stage" "$build" "$runtime"
runtime=$(realpath -e -- "$runtime")

git -C "$source_tree" archive "$expected_source_head" | tar -x -C "$stage"
mkdir -p "$stage/.deps/cutlass-sycl-src"
git -C "$cutlass_tree" archive "$expected_cutlass_head" |
  tar -x -C "$stage/.deps/cutlass-sycl-src"

# Reconstruction prerequisite: this reproduces the incumbent graph-safe
# launcher semantics. It is not part of the candidate policy delta.
(cd "$stage" && git apply "$local_accessor_patch")
(cd "$stage" && git apply --unidiff-zero "$candidate_patch")
grep -Fq 'VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY engaged' \
  "$stage/csrc/xpu/attn/xe_2/fmha_xe2.cpp" ||
  die 'staged selector marker is absent'
grep -Fq 'decode_policy_qpacked_head<_8, _256, _64>' \
  "$stage/csrc/xpu/attn/xe_2/m6_head256_chunk_prefill.cpp" ||
  die 'staged candidate policy is absent'

if [[ -f $compiler_root/env/vars.sh ]]; then
  set +u
  source "$compiler_root/env/vars.sh" >/dev/null
  set -u
fi

export VLLM_XPU_AOT_DEVICES=$aot_devices
export VLLM_XPU_XE2_AOT_DEVICES=$aot_devices
export VLLM_CUTLASS_SRC_DIR="$stage/.deps/cutlass-sycl-src"
cmake -S "$stage" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$stage/cmake/toolchain.cmake" \
  -DCMAKE_C_COMPILER="$compiler_root/bin/icx" \
  -DCMAKE_CXX_COMPILER="$compiler_root/bin/icpx" \
  -DVLLM_PYTHON_EXECUTABLE="$python_bin" \
  -DVLLM_TARGET_DEVICE=xpu \
  -DFETCHCONTENT_BASE_DIR="$stage/.deps" \
  -DBUILD_SYCL_TLA_KERNELS=ON \
  -DVLLM_XPU_ENABLE_XE2=ON \
  -DVLLM_XPU_ENABLE_XE_DEFAULT=OFF \
  -DVLLM_CHUNK_PREFILL_CONFIG="$chunk_config" \
  -DVLLM_PAGED_DECODE_CONFIG="$paged_config" \
  -DBASIC_KERNELS_ENABLED=OFF \
  -DFA2_KERNELS_ENABLED=ON \
  -DMOE_KERNELS_ENABLED=OFF \
  -DGDN_KERNELS_ENABLED=OFF \
  -DMQA_LOGITS_KERNELS_ENABLED=OFF \
  -DXPU_SPECIFIC_KERNELS_ENABLED=OFF \
  -DXPUMEM_ALLOCATOR_ENABLED=OFF

fmha_object=csrc/xpu/attn/xe_2/CMakeFiles/attn_kernels_xe_2.dir/fmha_xe2.cpp.o
candidate_object=csrc/xpu/attn/xe_2/CMakeFiles/attn_kernels_xe_2.dir/m6_head256_chunk_prefill.cpp.o
ninja -C "$build" -t targets all | grep -Fx "$fmha_object: CXX_COMPILER__attn_kernels_xe_2_unscanned_Release" >/dev/null ||
  die 'configured fmha object target is absent'
ninja -C "$build" -t targets all | grep -Fx "$candidate_object: CXX_COMPILER__attn_kernels_xe_2_unscanned_Release" >/dev/null ||
  die 'configured candidate object target is absent'
cmake --build "$build" --target "$fmha_object" "$candidate_object" --parallel 1

torch_lib=$(
  "$python_bin" -c \
    'from pathlib import Path; import torch; print(Path(torch.__file__).parent / "lib")'
)
[[ -d $torch_lib ]] || die "Torch library directory is absent: $torch_lib"

link_args=(
  -shared
  -fsycl
  -fsycl-max-parallel-link-jobs=1
  -flink-huge-device-code
  -Xspirv-translator
  -spirv-ext=+SPV_INTEL_split_barrier,+SPV_INTEL_2d_block_io,+SPV_INTEL_subgroup_matrix_multiply_accumulate
  -fsycl-targets=spir64_gen
  -Xsycl-target-backend=spir64_gen
  "-device $aot_devices -internal_options -cl-intel-256-GRF-per-thread"
  -Wl,-z,defs
  -Wl,-soname,libattn_kernels_xe_2.so
  "-Wl,-rpath,\$ORIGIN:$torch_lib"
  -o "$artifact"
  "$build/$fmha_object"
  "$build/$candidate_object"
  -Wl,--no-as-needed
  "$base_stage/vllm_xpu_kernels/libattn_stock.so"
  "$torch_lib/libtorch.so"
  "$torch_lib/libtorch_cpu.so"
  "$torch_lib/libtorch_xpu.so"
  "$torch_lib/libc10.so"
  "$torch_lib/libc10_xpu.so"
  "$compiler_root/lib/libsycl.so"
  -Wl,--as-needed
)
"$compiler_root/bin/icpx" "${link_args[@]}"

readelf -d "$artifact" | grep -F \
  'Library soname: [libattn_kernels_xe_2.so]' >/dev/null ||
  die 'candidate DSO has the wrong SONAME'
readelf -d "$artifact" | grep -F \
  'Shared library: [libattn_stock.so]' >/dev/null ||
  die 'candidate DSO does not retain the stock-attention dependency'
nm -D --defined-only "$artifact" | c++filt |
  grep -F 'cutlass_chunk_prefill_xe2(' >/dev/null ||
  die 'candidate DSO does not export cutlass_chunk_prefill_xe2'
nm -D --defined-only "$artifact" | c++filt |
  grep -F 'qwen38_m6_head256_q8k64_chunk_prefill(' >/dev/null ||
  die 'candidate dispatcher did not resolve into the candidate DSO'
if nm -D --undefined-only "$artifact" | c++filt |
  grep -F 'qwen38_m6_head256_q8k64_chunk_prefill(' >/dev/null; then
  die 'candidate dispatcher remains undefined after the fail-closed link'
fi
strings "$artifact" | grep -Fx \
  'VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY engaged' >/dev/null ||
  die 'candidate DSO does not contain the invariant engagement marker'

rsync -a "$base_stage/" "$runtime/"
install -m 0755 "$artifact" \
  "$runtime/vllm_xpu_kernels/libattn_kernels_xe_2.so"
verify_sha "$runtime/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" \
  "$expected_extension_sha"
verify_sha "$runtime/vllm_xpu_kernels/flash_attn_interface.py" \
  "$expected_wrapper_sha"
verify_sha "$runtime/vllm_xpu_kernels/libattn_stock.so" \
  "$expected_stock_sha"
readelf -d "$runtime/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" |
  grep -F 'Shared library: [libattn_kernels_xe_2.so]' >/dev/null ||
  die 'runtime extension-to-candidate dependency edge is absent'
readelf -d "$runtime/vllm_xpu_kernels/libattn_kernels_xe_2.so" |
  grep -F 'Shared library: [libattn_stock.so]' >/dev/null ||
  die 'runtime candidate-to-stock dependency edge is absent'
candidate_sha=$(sha256sum -- \
  "$runtime/vllm_xpu_kernels/libattn_kernels_xe_2.so" | awk '{print $1}')

graph_manifest="$WORK_ROOT/qwen38-m6-head256-q8k64-candidate.graph.sha256"
build_manifest="$WORK_ROOT/qwen38-m6-head256-q8k64-build-inputs.sha256"
stage_json="$WORK_ROOT/qwen38-m6-head256-q8k64-candidate-stage.json"
source_identity="$WORK_ROOT/qwen38-m6-head256-q8k64-source-identity.txt"
(
  cd "$runtime"
  find vllm_xpu_kernels -type f -print0 |
    LC_ALL=C sort -z |
    xargs -0 sha256sum > "$graph_manifest"
)
source_tree_oid=$(git -C "$source_tree" rev-parse "$expected_source_head^{tree}")
cutlass_tree_oid=$(git -C "$cutlass_tree" rev-parse "$expected_cutlass_head^{tree}")
printf '%s\n' \
  'schema=qwen38-m6-head256-q8k64-source-v1' \
  'staging_method=git-archive' \
  "vllm_xpu_kernels_commit=$expected_source_head" \
  "vllm_xpu_kernels_tree=$source_tree_oid" \
  "cutlass_sycl_commit=$expected_cutlass_head" \
  "cutlass_sycl_tree=$cutlass_tree_oid" > "$source_identity"
sha256sum -- \
  "$candidate_patch" \
  "$local_accessor_patch" \
  "$chunk_config" \
  "$paged_config" \
  "$stage/csrc/xpu/attn/xe_2/fmha_xe2.cpp" \
  "$stage/csrc/xpu/attn/xe_2/chunk_prefill.hpp" \
  "$stage/csrc/xpu/attn/xe_2/m6_head256_chunk_prefill.cpp" \
  "$stage/csrc/flash_attn/flash_api.cpp" \
  "$stage/CMakeLists.txt" \
  "$stage/cmake/utils.cmake" \
  "$stage/csrc/xpu/attn/xe_2/CMakeLists.txt" \
  "$build/$fmha_object" \
  "$build/$candidate_object" \
  "$artifact" \
  "$graph_manifest" \
  "$source_identity" \
  "$helper_path" > "$build_manifest"
chmod 0444 "$graph_manifest" "$source_identity" "$build_manifest"

extension_sha=$(sha256sum -- \
  "$runtime/vllm_xpu_kernels/_vllm_fa2_C.abi3.so" | awk '{print $1}')
interface_sha=$(sha256sum -- \
  "$runtime/vllm_xpu_kernels/flash_attn_interface.py" | awk '{print $1}')
stock_sha=$(sha256sum -- \
  "$runtime/vllm_xpu_kernels/libattn_stock.so" | awk '{print $1}')
build_manifest_sha=$(sha256sum -- "$build_manifest" | awk '{print $1}')

"$python_bin" - \
  "$stage_json" \
  "$runtime" \
  "$build_manifest" \
  "$build_manifest_sha" \
  "$extension_sha" \
  "$interface_sha" \
  "$candidate_sha" \
  "$stock_sha" <<'PY'
import json
import os
from pathlib import Path
import sys

(
    output_text,
    stage_text,
    artifact_text,
    artifact_sha,
    extension_sha,
    interface_sha,
    device_sha,
    stock_sha,
) = sys.argv[1:]
output = Path(output_text)
temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
payload = {
    "schema": "qwen38-mtp5-m6-fa-stage-v1",
    "role": "candidate",
    "stage": stage_text,
    "files": {
        "extension": {
            "relative_path": "vllm_xpu_kernels/_vllm_fa2_C.abi3.so",
            "sha256": extension_sha,
        },
        "interface": {
            "relative_path": "vllm_xpu_kernels/flash_attn_interface.py",
            "sha256": interface_sha,
        },
        "device_library": {
            "relative_path": "vllm_xpu_kernels/libattn_kernels_xe_2.so",
            "sha256": device_sha,
        },
        "stock_library": {
            "relative_path": "vllm_xpu_kernels/libattn_stock.so",
            "sha256": stock_sha,
        },
    },
    "artifact": {"path": artifact_text, "sha256": artifact_sha},
}
encoded = (
    json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
    + "\n"
).encode("utf-8")
file_descriptor = os.open(
    temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
)
try:
    with os.fdopen(file_descriptor, "wb", closefd=True) as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o444)
    os.replace(temporary, output)
    directory_descriptor = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
except BaseException:
    try:
        temporary.unlink()
    except FileNotFoundError:
        pass
    raise
PY

"$python_bin" - "$qualifier" "$stage_json" <<'PY'
import importlib.util
from pathlib import Path
import sys

qualifier_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("qwen38_m6_stage_validator", qualifier_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load qualifier: {qualifier_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
identity = module.validate_candidate_manifest(manifest_path)
if identity["stage"] != str(manifest_path.parent / "runtime"):
    raise RuntimeError("validated candidate stage path differs from helper output")
PY

printf 'PASS: built two-object, stock-dependent attention override at %s\n' \
  "$runtime"
printf 'candidate_sha256=%s\n' "$candidate_sha"
printf 'graph_manifest=%s\n' "$graph_manifest"
printf 'build_inputs_manifest=%s\n' "$build_manifest"
printf 'source_identity=%s\n' "$source_identity"
printf 'candidate_stage_json=%s\n' "$stage_json"
printf 'local_accessor_patch=reconstruction prerequisite, not candidate delta\n'
printf 'selector=VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY\n'
printf 'selector_off=incumbent dispatcher; selector_on=exact M6/head256 shape only\n'
