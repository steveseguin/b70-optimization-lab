#!/bin/bash
# Final series on the c5 build (canonical + dense-raw.patch): interleaved timing at 4096 rows / 256-row chunks, each run
# gated against ref-a; the switch-off gate; the 300-row gate pair. No builds or other host work while it runs.
cd /dev/shm/ownrt-lab-raw
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
gate(){ python3 -B $D compare runs/$1 runs/$2 | head -c 170; echo; python3 -c "
import json;a=json.load(open('runs/$1/summary.json'));b=json.load(open('runs/$2/summary.json'));print('tokens_equal',a['tokens']==b['tokens'])"; }
./run.sh f-raw0 raw5 4096 256 || exit 1; gate ref-a f-raw0; rm -rf runs/f-raw0/rank1/state-2147483647   # warm JIT for c5
for i in 1 2 3; do
  ./run.sh f-ref$i ref 4096 256 || exit 1; gate ref-a f-ref$i; rm -rf runs/f-ref$i/rank1/state-2147483647
  ./run.sh f-raw$i raw5 4096 256 || exit 1; gate ref-a f-raw$i; rm -rf runs/f-raw$i/rank1/state-2147483647
done
./run.sh f-off raw5 4096 256 OWNRT_DENSE_RAW=0 || exit 1; gate ref-a f-off; rm -rf runs/f-off/rank1/state-2147483647
./run.sh f-ref300 ref 300 256 || exit 1
./run.sh f-raw300 raw5 300 256 || exit 1; gate f-ref300 f-raw300; rm -rf runs/f-raw300/rank1/state-2147483647
echo ALL-DONE
