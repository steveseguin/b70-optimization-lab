#!/usr/bin/env bash
# Build recipe of research/p2p/direct-store-2026-10-28/build.sh (oneAPI 2026.0 icpx, JIT spir64, -O2 -std=c++20) for the
# pair copy. CPU only.
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$D/bin"
set +u; source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1; set -u
icpx --version | head -1
icpx -fsycl -O2 -std=c++20 "$D/p2p_direct_store_pair.cpp" -o "$D/bin/p2p_direct_store_pair"
sha256sum "$D/bin/p2p_direct_store_pair"
