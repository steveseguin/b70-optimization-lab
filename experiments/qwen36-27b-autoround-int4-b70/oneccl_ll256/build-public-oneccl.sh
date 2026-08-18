#!/usr/bin/env bash
set -euo pipefail

# Build the public oneCCL revision that fixes the Qwen27 TP2 graph-replay
# oracle. The output stays outside Git; this script and the source patches are
# the reproducible artifact.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TOP_COMMIT="b52f40c07f0b140e6aba87548c80720a350a9827"
LIBCCL_COMMIT="4ceafd15c03ce46f11eeaf91781a92afebd3cecf"
SOURCE_DIR="${ONECCL_SOURCE_DIR:-/tmp/oneccl-public-qwen27}"
BUILD_DIR="${ONECCL_BUILD_DIR:-/tmp/oneccl-public-qwen27-build}"
INSTALL_DIR="${ONECCL_INSTALL_DIR:-$BUILD_DIR/install}"
JOBS="${JOBS:-24}"
APPLY_SEQUENCE_DEPENDENCY="${APPLY_SEQUENCE_DEPENDENCY:-0}"

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  git clone --recurse-submodules https://github.com/uxlfoundation/oneCCL.git \
    "$SOURCE_DIR"
  git -C "$SOURCE_DIR" checkout --detach "$TOP_COMMIT"
  git -C "$SOURCE_DIR" submodule update --init --recursive deps/libccl
fi

actual_top="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
actual_libccl="$(git -C "$SOURCE_DIR/deps/libccl" rev-parse HEAD)"
if [[ "$actual_top" != "$TOP_COMMIT" || "$actual_libccl" != "$LIBCCL_COMMIT" ]]; then
  printf 'unexpected oneCCL source identity: top=%s libccl=%s\n' \
    "$actual_top" "$actual_libccl" >&2
  exit 2
fi

apply_once() {
  local patch_file="$1"
  if git -C "$SOURCE_DIR/deps/libccl" apply --check "$patch_file" 2>/dev/null; then
    git -C "$SOURCE_DIR/deps/libccl" apply "$patch_file"
  elif ! git -C "$SOURCE_DIR/deps/libccl" apply --reverse --check \
      "$patch_file" 2>/dev/null; then
    printf 'patch is neither applicable nor already applied: %s\n' \
      "$patch_file" >&2
    exit 3
  fi
}

remove_once() {
  local patch_file="$1"
  if git -C "$SOURCE_DIR/deps/libccl" apply --reverse --check \
      "$patch_file" 2>/dev/null; then
    git -C "$SOURCE_DIR/deps/libccl" apply --reverse "$patch_file"
  elif ! git -C "$SOURCE_DIR/deps/libccl" apply --check \
      "$patch_file" 2>/dev/null; then
    printf 'patch is neither absent nor cleanly removable: %s\n' \
      "$patch_file" >&2
    exit 4
  fi
}

apply_once \
  "$ROOT/patches/qwen36-27b-autoround-int4-b70/oneccl-4ceafd1-intel-2025.3-build-compat.patch"
sequence_patch="$ROOT/patches/qwen36-27b-autoround-int4-b70/oneccl-recorded-ll256-sequence-dependency-inconclusive-20260711.patch"
if [[ "$APPLY_SEQUENCE_DEPENDENCY" == "1" ]]; then
  apply_once "$sequence_patch"
else
  # Reused source trees must not silently retain the optional experiment.
  remove_once "$sequence_patch"
fi

cmake -S "$SOURCE_DIR/deps/libccl" -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2025.3/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2025.3/bin/icpx \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
  -DCOMPUTE_BACKEND=dpcpp \
  -DCCL_ENABLE_ARCB=ON \
  -DBUILD_EXAMPLES=OFF \
  -DBUILD_FT=OFF \
  -DBUILD_CONFIG=ON \
  -DENABLE_MPI=ON \
  -DENABLE_MPI_TESTS=OFF \
  -DENABLE_PMIX=ON \
  -DENABLE_UMF=ON \
  -DENABLE_ESIMD=ON
cmake --build "$BUILD_DIR" --target install -j "$JOBS"

sha256sum "$INSTALL_DIR/lib/libccl.so.1.0" \
  "$INSTALL_DIR/lib/ccl/kernels/kernels.spv"
