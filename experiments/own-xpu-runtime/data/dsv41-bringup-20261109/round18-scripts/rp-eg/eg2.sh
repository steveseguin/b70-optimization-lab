#!/bin/bash
# eg2: engram gate fast bracket incl. the work-group forms (bench_engram_ff); 230 W card + clock sampler
W=/home/steve/dsv41-work; D=$W/eg/${RUN:-r2}; mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
t0=$(date '+%Y-%m-%d %H:%M:%S')
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 900 $W/eg/bench_engram_ff > $D/bench_engram_ff.txt 2>&1; echo "exit $?" >> $D/bench_engram_ff.txt
kill $SP
journalctl -k --since "$t0" -o cat | grep -iE "$J" | sed 's/^/FAULT: /' >> $D/faults.txt
echo DONE >> $D/done.txt
