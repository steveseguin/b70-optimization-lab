#!/bin/bash
cd /dev/shm/ownrt-lab-s23
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
tok(){ python3 -c "
import json;a=json.load(open('runs/$1/summary.json'));b=json.load(open('runs/$2/summary.json'));print('tokens_equal $1 $2',a['tokens']==b['tokens'])"; }
./run.sh ref24c ref 4096 256 || exit 1
./run.sh b24 newb 4096 256 || exit 1
python3 compare_ring.py runs/ref24c runs/b24 $((4096+48)); tok ref24c b24; rm -rf runs/b24/rank1/state-2147483647
./run.sh boff24 offb 4096 256 || exit 1
python3 -B $D compare runs/ref24c runs/boff24 | head -c 200; echo; tok ref24c boff24; rm -rf runs/boff24/rank1/state-2147483647 runs/ref24c/rank1/state-2147483647
./run.sh b23 newb 4096 256 SPLIT=23 || exit 1; rm -rf runs/b23/rank1/state-2147483647
echo ALL-DONE
