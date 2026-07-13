#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
llama_root="${LLAMA_ROOT:-/home/steve/src/llama.cpp}"
build_dir="${LLAMA_BUILD_DIR:-$llama_root/build-sycl-b70-qwen36-mtp-jit}"
out_dir="${XE2_VERIFIER_OUT:-/mnt/fast-ai/bench-results/qwen27-xe2-verifier}"
binary="$out_dir/production-comparator-slm-v3"

mkdir -p "$out_dir"

# shellcheck disable=SC1091
set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u

icpx -fsycl -fsycl-targets=spir64_gen \
  -Xs "-device ${XE2_DEVICE_TARGET:-bmg-g31}" \
  -O3 -DNDEBUG -DGGML_SYCL_WARP_SIZE=32 -std=c++17 \
  -I"$llama_root/ggml/include" \
  -I"$llama_root/ggml/src" \
  -I"$llama_root/ggml/src/ggml-sycl" \
  "$here/production-comparator-v3.cpp" \
  -L"$build_dir/bin" \
  -Wl,-rpath,"$build_dir/bin" \
  -lggml-sycl \
  -o "$binary"

echo "compiled=$binary"

if [[ "${XE2_COMPILE_ONLY:-0}" == 1 ]]; then
  exit 0
fi

: "${ZE_AFFINITY_MASK:?Set ZE_AFFINITY_MASK to one explicitly reserved B70}"

for width in ${XE2_WIDTHS:-6 9 16}; do
  for shape in ${XE2_SHAPES:-5120x5120 5120x17408 17408x5120}; do
    k="${shape%x*}"
    n="${shape#*x}"
    "$binary" "$width" "$k" "$n" "${XE2_ITERS:-30}" || true
  done
done

