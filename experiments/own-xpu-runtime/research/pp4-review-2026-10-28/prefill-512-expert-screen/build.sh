#!/bin/bash
# Root coordinator only, after current build releases resources. Not run yet.
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
runtime=$(cd -- "$here/../../.." && pwd)
: "${1:?fresh existing output directory required}"
exec /opt/intel/oneapi/compiler/2026.0/bin/icpx -std=gnu++20 -O2 -g0 -Werror=return-type -fno-fast-math -ffp-contract=off -fsycl -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt -ffunction-sections -fdata-sections -I "$runtime/engine/src" "$here/screen.cpp" "$runtime/engine/src/stage2/packet2/loader/gguf.cpp" -Wl,--gc-sections -lze_loader -o "$1/screen"
