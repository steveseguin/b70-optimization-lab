#!/bin/bash
# 1015-p51b-WS128: SPEED6 WS128, first card 2, context 4096, draft rank 1, target split 23, seal 34c62b433
cd /home/steve/llm-optimizations
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
P=experiments/own-xpu-runtime/stage2/packet45-merged3
OUT=$P/build/speed6-c4096-dr1-s23-cards23-gpu
LOG=/tmp/claude-1000/-home-steve/0f73c5fb-e91f-453d-8cf4-02114dedd97b/scratchpad/1015-p51b-WS128
{ echo "start $(date -u +%FT%TZ)"
taskset -c 0-3,16-19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$P/window.py" --authorized-device-window --card 2 --context 4096 --draft-rank 1 --target-split 23 --window WS128 --output "$OUT/WS128" --k0 "$OUT/K0/window.json" --k1a "$OUT/K1a/window.json" --k1b "$OUT/K1b/window.json" --k2 "$OUT/K2/window.json" --w0p "$OUT/W0p/window.json" --kd "$OUT/KD/window.json" --dispatch "$OUT/K2/run0/dispatch-measured.json" --suite-manifest experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json --controller native --repeat 1 --exactness-window experiments/own-xpu-runtime/stage2/packet45-merged3/build/speed6-c4096-dr1-s23-cards23-gpu/WS128x/window.json 2>&1 | tail -40
echo "rc=${PIPESTATUS[0]} $(date -u +%FT%TZ)"
} > "$LOG.log" 2>&1
echo done > "$LOG.rc"
