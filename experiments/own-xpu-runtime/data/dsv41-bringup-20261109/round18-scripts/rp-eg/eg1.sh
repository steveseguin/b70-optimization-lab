#!/bin/bash
# eg1: engram gate fast bracket (bench_engram_ff) + router re-check (bench_route_rows rt6, bench_route_pick rp4); 230 W card + clock sampler
W=/home/steve/dsv41-work; D=$W/eg/${RUN:-r1}; mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
t0=$(date '+%Y-%m-%d %H:%M:%S')
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
for b in eg/bench_engram_ff bench_route_rows rp/bench_route_pick; do
  n=$(basename $b)
  ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 900 $W/$b > $D/$n.txt 2>&1; echo "exit $?" >> $D/$n.txt
  if journalctl -k --since "$t0" -o cat | grep -qiE "$J"; then echo "FAULT after $n" >> $D/$n.txt; break; fi
done
kill $SP
journalctl -k --since "$t0" -o cat | grep -iE "$J" | sed 's/^/FAULT: /' >> $D/faults.txt
echo DONE >> $D/done.txt
