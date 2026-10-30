#!/usr/bin/env bash
# One-card kbench run on 0000:23:00.0 (index 0 in PCI order), inside systemd-run holding /dev/shm/card23.lock.
set -u
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/fixed-cost-2026-10-30
export LD_LIBRARY_PATH='/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib'
export ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 ZE_AFFINITY_MASK=0 ONEAPI_DEVICE_SELECTOR='level_zero:*' NEOReadDebugKeys=1 EnableDeferBacking=0
"$1" > "$D/results/$2.txt" 2> "$D/logs/$2.stderr"; echo "rc=$?" >> "$D/logs/$2.stderr"
