#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
: "${EXACT_TP2_CXX:=/opt/intel/oneapi/compiler/2026.1/bin/icpx}"
: "${EXACT_TP2_BUILD_DIR:=/tmp/mtp-exact-tp2-build-20260914}"
mkdir -p "$EXACT_TP2_BUILD_DIR"
"$EXACT_TP2_CXX" --version > "$EXACT_TP2_BUILD_DIR/compiler.txt"
# Compile only. No discovery executable, SYCL selector, GPU or container run.
"$EXACT_TP2_CXX" -O2 -std=c++17 -fPIC -shared -fsycl \
  -fsycl-targets=spir64 -fno-fast-math -ffp-contract=off \
  exact_tp2.cpp -lze_loader -o "$EXACT_TP2_BUILD_DIR/libexact_tp2.so"
sha256sum exact_tp2.cpp "$EXACT_TP2_BUILD_DIR/libexact_tp2.so" > "$EXACT_TP2_BUILD_DIR/hashes.txt"
