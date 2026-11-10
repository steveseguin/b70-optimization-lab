#!/bin/bash
# After e81b: build and run the multi-row indexer score test (tools/bench/test_index_score_m.cpp) on one 230 W card (level_zero:1 = 0000:23:00.0, as the engine numbers them), with the clock sampler.
# Exits if e81b stopped. Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e81b/summary.txt 2>/dev/null; do sleep 10; done
grep -q STOP $S/runs/e81b/summary.txt && exit 1
while systemctl --user is-active --quiet dsv41-e81b; do sleep 2; done
D=$S/runs/e81c
mkdir -p $D
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
cd /home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
t0=$(date +%s)
icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
  "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
  -Wno-deprecated-declarations -I src tools/bench/test_index_score_m.cpp -o $S/test_index_score_m > $D/build.log 2>&1
echo "build exit $? in $(( $(date +%s) - t0 )) s" >> $sum
[ -x $S/test_index_score_m ] || { echo STOP_BUILD >> $sum; exit 1; }
tg=$(date '+%Y-%m-%d %H:%M:%S')
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 600 $S/test_index_score_m > $D/bench.txt 2>&1
echo "bench exit $?" >> $sum
kill $SP 2>/dev/null
f=$(journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3)
[ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
echo ALLDONE >> $sum
