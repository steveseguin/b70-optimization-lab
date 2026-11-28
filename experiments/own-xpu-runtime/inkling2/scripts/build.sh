#!/bin/bash
# build.sh <tool> [out]: compile tools/<tool>.cpp for the B70 with the engine's numerics:
#   -fp-model=precise, correctly rounded fp32 division and square root on the card, no multiply-add contraction.
# Every kernel then follows IEEE single precision op by op, so two kernels with the same arithmetic give the same bits
# whatever the code around them (the default fast model let one kernel's sqrt/div differ from another's).
# INK_CFLAGS: extra compiler flags (e.g. -DINK_NO_FMA: products rounded before the addition, baselines v1/v2).
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
tool=$1
out=${2:-/home/steve/inkling-work/bin/$tool}
set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1; set -u
avail=$(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo)
[ "$avail" -ge 6 ] || { echo "build: only $avail GiB host memory available (need 6)"; exit 3; }
if [ -z "${TMPDIR:-}" ] && [ -d /mnt/fast-ai/inkling-cache ]; then
    mkdir -p /mnt/fast-ai/inkling-cache/tmp
    export TMPDIR=/mnt/fast-ai/inkling-cache/tmp
fi
extra=()
case $tool in test_formats|test_gemv) R=${INK_REF:-/home/steve/inkling-work/ref-src/llama.cpp-b12588-mix-c0c3de8}
    extra=(-I "$R/ggml/include" "$R/build/ggml/src/libggml-base.a" "$(gcc -print-file-name=libgomp.so)" -lpthread -lm) ;;
esac
src="$here/tools/$tool.cpp"
[ -f "$src" ] || src="$here/tools/benches/$tool.cpp"
[ -f "$src" ] || { echo "build: source not found in tools/ or tools/benches/ for '$tool'"; exit 2; }
set +e
icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -foffload-fp32-prec-div -foffload-fp32-prec-sqrt \
    -Wno-overriding-option -fsycl-targets=intel_gpu_bmg_g31 ${INK_CFLAGS:-} "$src" "${extra[@]}" -o "$out" 2>&1 \
    | grep -vE "Compilation from IR|Build succeeded|^$"
rc=${PIPESTATUS[0]}
set -e
[ "$rc" -eq 0 ] || { echo "build: icpx exited $rc"; exit "$rc"; }
[ -x "$out" ] || { echo "build: no executable at $out"; exit 1; }
echo "built $out"
