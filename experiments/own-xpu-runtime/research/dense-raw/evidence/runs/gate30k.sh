#!/bin/bash
cd /dev/shm/ownrt-lab-raw
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
./run.sh g-ref30k ref 30000 256 || exit 1
./run.sh g-raw30k raw5 30000 256 || exit 1
python3 -B $D compare runs/g-ref30k runs/g-raw30k | head -c 170; echo
python3 -c "
import json;a=json.load(open('runs/g-ref30k/summary.json'));b=json.load(open('runs/g-raw30k/summary.json'));print('tokens_equal',a['tokens']==b['tokens'])"
rm -rf runs/g-ref30k/rank1/state-2147483647 runs/g-raw30k/rank1/state-2147483647
echo ALL-DONE
