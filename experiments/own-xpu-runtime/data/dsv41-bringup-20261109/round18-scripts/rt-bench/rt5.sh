#!/bin/bash
# rt5: what sets the router launch time (tools/bench/bench_route_rows.cpp), 230 W card + clock sampler
W=/home/steve/dsv41-work; D=$W/runs/r5; mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
t0=$(date '+%Y-%m-%d %H:%M:%S')
ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 600 $W/bench_route_rows > $D/out.txt 2>&1; echo "exit $?" >> $D/out.txt
kill $SP
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
journalctl -k --since "$t0" -o cat | grep -iE "$J" | sed 's/^/FAULT: /' >> $D/out.txt
echo DONE >> $D/out.txt
