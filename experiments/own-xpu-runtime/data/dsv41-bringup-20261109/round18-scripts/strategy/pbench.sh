#!/bin/bash
# pbench.sh RUNDIR "card|binary|args" ... : one-card benches on different cards AT THE SAME TIME (one process per
# card), each with its own clock sampler line in the telemetry; stops nothing on a fault (each bench is short) but
# records fault lines. Use only when no six-card run is active.
W=/home/steve/dsv41-work; D=$1; shift; mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
t0=$(date '+%Y-%m-%d %H:%M:%S')
pids=()
for spec in "$@"; do
  IFS='|' read -r card bin args <<< "$spec"
  name=$(basename $bin)_c${card}_$(echo "$args" | tr ' /' '__')
  ( ONEAPI_DEVICE_SELECTOR=level_zero:$card timeout 600 $bin $args > $D/$name.txt 2>&1; echo "exit $?" >> $D/$name.txt ) &
  pids+=($!)
done
for p in "${pids[@]}"; do wait $p; done
kill $SP
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
journalctl -k --since "$t0" -o cat | grep -iE "$J" | sed 's/^/FAULT: /' > $D/faults.txt
echo DONE > $D/done.txt
