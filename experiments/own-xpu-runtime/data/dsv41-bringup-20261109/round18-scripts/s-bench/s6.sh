#!/bin/bash
# s6: the softmax fused into the JC attention output (tools/bench/bench_sparse_out_fused.cpp), 230 W card + clock sampler
W=/home/steve/dsv41-work; D=$W/runs/s6
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/bench_sparse_out_fused > $D/out.txt 2>&1; echo "exit $?" >> $D/out.txt
kill $SP
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
journalctl -k --since "-10 min" -o cat | grep -iE "$J" | sed 's/^/FAULT: /' >> $D/out.txt
echo DONE >> $D/out.txt
