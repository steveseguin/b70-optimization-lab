#!/bin/bash
cd /dev/shm/ownrt-lab-raw
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
for cfg in "211 121" "411 221" "412 141" "111 211" "811 111"; do set -- $cfg
  n=p4-$1-$2
  ./run.sh $n raw4 4096 256 OWNRT_DECODE_PROFILE=2 OWNRT_DENSE_RAW_Q6=$1 OWNRT_DENSE_RAW_Q8=$2 || exit 1
  python3 -B $D compare runs/ref-a runs/$n | head -c 160; echo
  rm -rf runs/$n/rank1/state-2147483647
done
echo ALL-DONE
