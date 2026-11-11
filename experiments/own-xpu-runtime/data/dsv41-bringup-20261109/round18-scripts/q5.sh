#!/bin/bash
# q5: test_topk_q with lengths up to 139,000 rows (TopKSelBQ<32> past 131,072; the row selects' fallback past 98,304)
W=/home/steve/dsv41-work; D=$W/runs/q5; mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 & SP=$!
ONEAPI_DEVICE_SELECTOR=level_zero:1 $W/test_topk_q > $D/out.txt 2>&1; echo "exit $?" >> $D/out.txt
kill $SP
echo DONE >> $D/out.txt
