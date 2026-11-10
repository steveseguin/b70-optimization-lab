#!/bin/bash
# The load-first copy (XchgPull::copy_lb): exchange latency (xchg_lat_bench) and correctness under changing data
# (xchg_pull_test: the engine's XchgPull, now copy_lb by default) on the six idle cards. Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e81d
mkdir -p $D
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
cd /home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
for b in xchg_lat_bench xchg_pull_test; do
  icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src \
    tools/bench/$b.cpp -o $S/$b -lze_loader > $D/build-$b.log 2>&1
  echo "build $b exit $?" >> $sum
done
tg=$(date '+%Y-%m-%d %H:%M:%S')
NEOReadDebugKeys=1 DisableIndirectAccess=1 timeout 300 $S/xchg_lat_bench 2000 > $D/lat.txt 2>&1
echo "lat exit $?" >> $sum
f=$(journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3)
[ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
NEOReadDebugKeys=1 DisableIndirectAccess=1 timeout 600 $S/xchg_pull_test 2000 > $D/pull-test.txt 2>&1
echo "pull test exit $?" >> $sum
f=$(journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3)
[ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
echo ALLDONE >> $sum
