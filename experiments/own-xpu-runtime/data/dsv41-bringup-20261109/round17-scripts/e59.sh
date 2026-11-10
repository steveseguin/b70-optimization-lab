#!/bin/bash
# after e58: the row-block dense bench again, read-only eviction (bench_dense_rowblock2), card 0
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
while systemctl --user is-active -q dsv41-e58; do sleep 3; done
D=$S/runs/e59; mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
t0=$(date '+%Y-%m-%d %H:%M:%S')
$S/bench_dense_rowblock3 0 > $D/bench3.log 2>&1; echo "bench3 exit $?" >> $D/summary.txt
journalctl -k --since "$t0" -o cat | grep -iE 'fault response|cat error|engine reset|coredump has been created|gt reset' | head -3 >> $D/summary.txt
echo ALLDONE >> $D/summary.txt
