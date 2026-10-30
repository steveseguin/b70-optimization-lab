#!/usr/bin/env bash
# Build the HC kernel bench (CPU only). Engine headers come from ENGINE_SRC (default: the private copy of the committed
# engine/src made for this study, /dev/shm/hc-kernels-2026-10-30/engine/.../engine/src at BASE_COMMIT).
# Flags as the engine's translation units; offload precision flags also on the link line.
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-/dev/shm/hc-kernels-2026-10-30/build}
ENGINE_SRC=${ENGINE_SRC:-/dev/shm/hc-kernels-2026-10-30/engine/experiments/own-xpu-runtime/engine/src}
mkdir -p "$OUT"
CXX=/opt/intel/oneapi/compiler/2026.0/bin/icpx
FLAGS=(-std=gnu++20 -O2 -g0 -fno-fast-math -ffp-contract=off -fsycl -fdenormal-fp-math=ieee
       -foffload-fp32-prec-div -foffload-fp32-prec-sqrt)
LINK=(-fsycl -foffload-fp32-prec-div -foffload-fp32-prec-sqrt -fno-fast-math)
for src in ${@:-hc_bench}; do
  nice -n 19 taskset -c 8-15,24-31 "$CXX" "${FLAGS[@]}" -I "$D" -I "$ENGINE_SRC" -c "$D/$src.cpp" -o "$OUT/$src.o"
  nice -n 19 taskset -c 8-15,24-31 "$CXX" "${LINK[@]}" "$OUT/$src.o" -o "$OUT/$src"
  sha256sum "$OUT/$src" | tee "$OUT/$src.sha256"
done
