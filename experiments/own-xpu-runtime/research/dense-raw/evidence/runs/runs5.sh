#!/bin/bash
cd /dev/shm/ownrt-lab-raw
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
for cfg in "121 121 1" "141 111 0"; do set -- $cfg
  n=p4-$1-$2-v$3
  ./run.sh $n raw4 4096 256 OWNRT_DECODE_PROFILE=2 OWNRT_DENSE_RAW_Q6=$1 OWNRT_DENSE_RAW_Q8=$2 OWNRT_DENSE_RAW_VERIFY=$3 || exit 1
  python3 -B $D compare runs/ref-a runs/$n | head -c 160; echo
  rm -rf runs/$n/rank1/state-2147483647
done
echo ALL-DONE
