#!/bin/bash
# 977-p44ctlc-WS128r2: same-session packet-44 control repeat (WS128, cards 0-1, context 4096) between SPEED3 repeats; chain receipts in c4096ctl15a
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
cd /home/steve/llm-optimizations
packet44=experiments/own-xpu-runtime/stage2/packet44-context
packet44_card=0
packet44_context=4096
packet44_out="$packet44/build/c4096ctl15a"
packet44_input="$packet44/build/input"
packet44_oracle=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
suite128=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
LOG=/tmp/claude-1000/-home-steve/0f73c5fb-e91f-453d-8cf4-02114dedd97b/scratchpad/977-p44ctlc-WS128r2
{ echo "start $(date -u +%FT%TZ)"
taskset -c 0-3,16-19 ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet44/window.py" --authorized-device-window --card "$packet44_card" --context "$packet44_context" --window WS --output "$packet44_out/WS128-r2" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --w0p "$packet44_out/W0p/window.json" --kd "$packet44_out/KD/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --suite-manifest "$suite128" --controller native --repeat 1 2>&1 | tail -n 40
echo "rc=${PIPESTATUS[0]} $(date -u +%FT%TZ)"
} > "$LOG.log" 2>&1
echo done > "$LOG.rc"
