#!/usr/bin/env bash
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_tree=${SOURCE_TREE:-/home/steve/src/vllm-xpu-kernels}
stage=${STAGE_DIR:-$here/work/source}
build=${BUILD_DIR:-$here/work/build}
python=${PYTHON:-/home/steve/.venvs/vllm-xpu/bin/python}
jobs=${MAX_JOBS:-8}
compiler_root=${INTEL_COMPILER_ROOT:-/opt/intel/oneapi/compiler/2025.3}
chunk_config=${VLLM_CHUNK_PREFILL_CONFIG:-$here/qwen38-head256-chunk.conf}
paged_config=${VLLM_PAGED_DECODE_CONFIG:-$here/qwen38-head256-paged.conf}
cc=${CC:-$compiler_root/bin/icx}
cxx=${CXX:-$compiler_root/bin/icpx}
full=0

if [[ ${1:-} == --full ]]; then
  full=1
elif [[ $# -ne 0 ]]; then
  printf 'usage: %s [--full]\n' "$0" >&2
  exit 2
fi

case "$stage" in
  "$here"/work/*) ;;
  *) printf 'STAGE_DIR must remain under %s/work\n' "$here" >&2; exit 2 ;;
esac
case "$build" in
  "$here"/work/*) ;;
  *) printf 'BUILD_DIR must remain under %s/work\n' "$here" >&2; exit 2 ;;
esac

test -f "$source_tree/csrc/xpu/attn/xe_2/chunk_prefill.hpp"
test -x "$python"
test -x "$cc"
test -x "$cxx"
test -f "$chunk_config"
test -f "$paged_config"
command -v rsync >/dev/null

rm -rf -- "$stage" "$build"
mkdir -p -- "$stage" "$build"
rsync -a \
  --exclude '/.git' \
  --exclude '/build' \
  --exclude '/.deps/*-build' \
  --exclude '/.deps/*-subbuild' \
  --exclude '*.so' \
  --exclude '*.so.*' \
  "$source_tree/" "$stage/"
git -C "$source_tree" apply --check \
  "$here/qwen27-chunk-prefill-local-accessor.patch"
patch -d "$stage" -p1 < "$here/qwen27-chunk-prefill-local-accessor.patch"
patch --dry-run -d "$stage" -p1 \
  < "$here/qwen27-chunk-prefill-completion-barrier.patch"
patch -d "$stage" -p1 \
  < "$here/qwen27-chunk-prefill-completion-barrier.patch"
git -C "$source_tree" apply --check "$here/qwen27-force-chunk-decode.patch"
patch -d "$stage" -p1 < "$here/qwen27-force-chunk-decode.patch"
git -C "$source_tree" apply --check \
  "$here/qwen27-force-chunk-decode-python.patch"
patch -d "$stage" -p1 < "$here/qwen27-force-chunk-decode-python.patch"

if [[ -f "$compiler_root/env/vars.sh" ]]; then
  # oneAPI's versioned setup script is not nounset-clean. Pinning this avoids
  # mixing 2026 device IR with the deployed 2025.3 attention objects.
  set +u
  source "$compiler_root/env/vars.sh" >/dev/null
  set -u
fi

cmake -S "$stage" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$stage/cmake/toolchain.cmake" \
  -DCMAKE_C_COMPILER="$cc" \
  -DCMAKE_CXX_COMPILER="$cxx" \
  -DVLLM_PYTHON_EXECUTABLE="$python" \
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

object_targets=(
  csrc/xpu/attn/xe_2/CMakeFiles/attn_kernels_xe_2.dir/chunk_prefill_kernel_template_chunk_policy_head256_ttfff.cpp.o
  csrc/xpu/attn/xe_2/CMakeFiles/attn_kernels_xe_2.dir/chunk_prefill_kernel_template_chunk_policy_head256_tffff.cpp.o
  CMakeFiles/_vllm_fa2_C.dir/csrc/flash_attn/flash_api.cpp.o
)
cmake --build "$build" --target "${object_targets[@]}" --parallel "$jobs"

if (( full )); then
  cmake --build "$build" --target attn_kernels_xe_2 _vllm_fa2_C \
    --parallel "$jobs"
  shopt -s nullglob
  extensions=("$build"/_vllm_fa2_C*.so)
  if [[ ${#extensions[@]} -ne 1 ]]; then
    printf 'expected one built _vllm_fa2_C extension, found %d\n' \
      "${#extensions[@]}" >&2
    exit 1
  fi
  install -m 0755 "${extensions[0]}" "$stage/vllm_xpu_kernels/"
  install -m 0755 "$build/libattn_kernels_xe_2.so" \
    "$stage/vllm_xpu_kernels/"
fi

printf 'Build passed in %s\n' "$build"
