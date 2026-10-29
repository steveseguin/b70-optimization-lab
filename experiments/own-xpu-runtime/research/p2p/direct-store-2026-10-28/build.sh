#!/usr/bin/env bash
# Build recipe (same as research/p2p/*.cpp on 2026-10-25): oneAPI 2026.0 icpx, JIT spir64, -O2 -std=c++20.
set -euo pipefail
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/p2p/direct-store-2026-10-28
E=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/src
P=$E/stage2/packet194-expert-diet-engine
mkdir -p "$D/bin"
set +u; source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1; set -u
icpx --version | head -1
# 1. kernel-direct exchange microbenchmark
icpx -fsycl -O2 -std=c++20 "$D/p2p_direct_store.cpp" -o "$D/bin/p2p_direct_store"
# 2. engine owner-layer copy-engine peer_copy comparison (unchanged source, flags from the 2026-10-25 build)
F="-std=gnu++20 -O2 -g0 -DP56X_SLEEP20=0 -Werror=return-type -fno-fast-math -ffp-contract=off -fsycl -fdenormal-fp-math=ieee -I $E"
icpx $F /home/steve/llm-optimizations/experiments/own-xpu-runtime/research/p2p/owner_peer.cpp \
  $P/owner.cpp $P/owner_retire.cpp $P/single_device.cpp $P/host_wait_mode.cpp -lze_loader -o "$D/bin/owner_peer"
ls -la "$D/bin"
