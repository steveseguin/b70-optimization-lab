#!/bin/bash
# q2: test_topk_z (forms of the top-512 select, bitwise vs TopKSelP) on one 230 W card with the clock sampler.
set -u
W=/home/steve/dsv41-work; E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine; D=$W/runs/q2
sum=$D/summary.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
(cd $E && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src $D/test_topk_z.cpp -o $W/test_topk_z > $D/build.log 2>&1)
rc=$?; echo "test_topk_z build exit $rc in $(( $(date +%s) - t0 )) s" >> $sum; [ $rc -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
trap 'kill $SP 2>/dev/null' EXIT
tg=$(date '+%Y-%m-%d %H:%M:%S')
ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/test_topk_z > $D/test_topk_z.txt 2>&1; echo "test_topk_z exit $?: $(tail -1 $D/test_topk_z.txt)" >> $sum
f=$(journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
echo ALLDONE >> $sum
