#!/bin/bash
# 947-p45a-chain: packet 45 helper chain, first card 0, context 4096, draft rank 0
cd /home/steve/llm-optimizations
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
LOG=/tmp/claude-1000/-home-steve/0f73c5fb-e91f-453d-8cf4-02114dedd97b/scratchpad/947-p45a-chain
{ echo "start $(date -u +%FT%TZ)"
taskset -c 0-3,16-19 ionice -c 3 bash experiments/own-xpu-runtime/stage2/packet45-merged3/coordinator_windows.sh 0 4096 0 experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json experiments/own-xpu-runtime/stage2/packet45-merged3/build/c4096-dr0-gpu 2>&1 | tail -40
echo "rc=${PIPESTATUS[0]} $(date -u +%FT%TZ)"
} > "$LOG.log" 2>&1
echo done > "$LOG.rc"
