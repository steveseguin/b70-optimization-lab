#!/usr/bin/env bash
# Build the persistent-layer microbenchmarks with the host's oneAPI 2026.0 icpx (CPU only; never runs a binary).
# Flags follow the engine's translation units: precise FP, no contraction, IEEE denormals, and the offload
# precision flags on the compile AND the link line (they only take effect on the device image when linked with them).
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-/dev/shm/persistent-layer-2026-10-30}
mkdir -p "$OUT"
CXX=/opt/intel/oneapi/compiler/2026.0/bin/icpx
FLAGS=(-std=gnu++20 -O2 -g0 -fno-fast-math -ffp-contract=off -fsycl -fdenormal-fp-math=ieee
       -foffload-fp32-prec-div -foffload-fp32-prec-sqrt)
LINK=(-fsycl -foffload-fp32-prec-div -foffload-fp32-prec-sqrt -fno-fast-math)
for src in ${@:-barrier chain}; do
  nice -n 19 taskset -c 8-15,24-31 "$CXX" "${FLAGS[@]}" -I "$D" -I /home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/src \
    -c "$D/$src.cpp" -o "$OUT/$src.o"
  nice -n 19 taskset -c 8-15,24-31 "$CXX" "${LINK[@]}" "$OUT/$src.o" -o "$OUT/$src"
  sha256sum "$OUT/$src" | tee "$OUT/$src.sha256"
done
