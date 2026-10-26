#!/bin/bash
cd /dev/shm/ownrt-lab-s23
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
tok(){ python3 -c "
import json;a=json.load(open('runs/$1/summary.json'));b=json.load(open('runs/$2/summary.json'));print('tokens_equal',a['tokens']==b['tokens'])"; }
./run.sh ref24 ref 4096 256 || exit 1
./run.sh new24 new 4096 256 || exit 1
python3 compare_ring.py runs/ref24 runs/new24 $((4096+48)); tok ref24 new24
rm -rf runs/new24/rank1/state-2147483647
./run.sh off24 off 4096 256 || exit 1
python3 -B $D compare runs/ref24 runs/off24 | head -c 200; echo; tok ref24 off24
rm -rf runs/off24/rank1/state-2147483647
echo ALL-DONE
