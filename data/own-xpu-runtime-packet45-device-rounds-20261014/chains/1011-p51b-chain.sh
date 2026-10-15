#!/bin/bash
# 1011-p51b-chain: SPEED6 (23/25 split, draft rank 1), first card 2, context 4096, seal 34c62b433
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
cd /home/steve/llm-optimizations
LOG=/tmp/claude-1000/-home-steve/0f73c5fb-e91f-453d-8cf4-02114dedd97b/scratchpad/1011-p51b-chain
{ echo "start $(date -u +%FT%TZ)"
taskset -c 0-3,16-19 ionice -c 3 bash data/own-xpu-runtime-packet45-device-rounds-20261014/runner/coordinator_windows_speed5_omp2.sh 2 4096 1 experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json experiments/own-xpu-runtime/stage2/packet45-merged3/build/speed6-c4096-dr1-s23-cards23-gpu 23 2>&1 | tail -40
echo "rc=${PIPESTATUS[0]} $(date -u +%FT%TZ)"
} > "$LOG.log" 2>&1
echo done > "$LOG.rc"
