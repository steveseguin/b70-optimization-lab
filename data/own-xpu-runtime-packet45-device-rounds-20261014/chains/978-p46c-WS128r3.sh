#!/bin/bash
# 978-p46c-WS128r3: second confirmation repeat of SPEED3 WS128 (24/24, dr0, cards 0-1), seal 75d2c459d
cd /home/steve/llm-optimizations
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
P=experiments/own-xpu-runtime/stage2/packet45-merged3
OUT=$P/build/speed3-c4096-dr0-s24-gpu
LOG=/tmp/claude-1000/-home-steve/0f73c5fb-e91f-453d-8cf4-02114dedd97b/scratchpad/978-p46c-WS128r3
{ echo "start $(date -u +%FT%TZ)"
taskset -c 0-3,16-19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$P/window.py" --authorized-device-window --card 0 --context 4096 --draft-rank 0 --target-split 24 --window WS128 --output "$OUT/WS128-r3" --k0 "$OUT/K0/window.json" --k1a "$OUT/K1a/window.json" --k1b "$OUT/K1b/window.json" --k2 "$OUT/K2/window.json" --w0p "$OUT/W0p/window.json" --kd "$OUT/KD/window.json" --dispatch "$OUT/K2/run0/dispatch-measured.json" --suite-manifest experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json --controller native --repeat 1 --exactness-window experiments/own-xpu-runtime/stage2/packet45-merged3/build/speed3-c4096-dr0-s24-gpu/WS128x/window.json 2>&1 | tail -40
echo "rc=${PIPESTATUS[0]} $(date -u +%FT%TZ)"
} > "$LOG.log" 2>&1
echo done > "$LOG.rc"
