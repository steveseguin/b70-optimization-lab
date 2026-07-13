#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out_dir="${XE2_VERIFIER_OUT:-/mnt/fast-ai/bench-results/qwen27-xe2-verifier}"
binary="$out_dir/swiglu-q8-down-fusion"

mkdir -p "$out_dir"

# shellcheck disable=SC1091
set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
set -u

icpx -fsycl -fsycl-targets=spir64_gen \
  -Xs "-device ${XE2_DEVICE_TARGET:-bmg-g31}" \
  -O3 -DNDEBUG -std=c++17 \
  "$here/swiglu-q8-down-fusion.cpp" \
  -o "$binary"

echo "compiled=$binary"

if [[ "${XE2_COMPILE_ONLY:-0}" == 1 ]]; then
  exit 0
fi

: "${ZE_AFFINITY_MASK:?Set ZE_AFFINITY_MASK to one explicitly reserved B70}"
"$binary" "${XE2_ITERS:-50}"
