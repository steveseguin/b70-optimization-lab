#!/bin/bash
# After e81: build and run the exchange-latency bench (tools/bench/xchg_lat_bench.cpp) on the idle cards.
# Exits if e81 stopped. Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e81/summary.txt 2>/dev/null; do sleep 10; done
grep -q STOP $S/runs/e81/summary.txt && exit 1
while systemctl --user is-active --quiet dsv41-e81; do sleep 2; done
D=$S/runs/e81b
mkdir -p $D
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
cd /home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
t0=$(date +%s)
icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -Wno-deprecated-declarations -I src \
  tools/bench/xchg_lat_bench.cpp -o $S/xchg_lat_bench -lze_loader > $D/build.log 2>&1
echo "build exit $? in $(( $(date +%s) - t0 )) s" >> $sum
[ -x $S/xchg_lat_bench ] || { echo STOP_BUILD >> $sum; exit 1; }
tg=$(date '+%Y-%m-%d %H:%M:%S')
NEOReadDebugKeys=1 DisableIndirectAccess=1 timeout 300 $S/xchg_lat_bench 2000 > $D/bench.txt 2>&1
echo "bench exit $?" >> $sum
f=$(journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3)
[ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
echo ALLDONE >> $sum
