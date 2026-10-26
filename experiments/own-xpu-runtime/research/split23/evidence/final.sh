#!/bin/bash
cd /dev/shm/ownrt-lab-s23
tok(){ python3 -c "
import json;a=json.load(open('runs/$1/summary.json'));b=json.load(open('runs/$2/summary.json'));print('tokens_equal $1 $2',a['tokens']==b['tokens'])"; }
./run.sh ref24-300 ref 300 256 || exit 1
./run.sh new24-300 new 300 256 || exit 1
python3 compare_ring.py runs/ref24-300 runs/new24-300 $((300+48)); tok ref24-300 new24-300
rm -rf runs/ref24-300/rank1/state-2147483647 runs/new24-300/rank1/state-2147483647
./run.sh ref23k32-30k ref 30000 256 SPLIT=23 CONTEXT=32768 || exit 1
./run.sh new23-30k new 30000 256 SPLIT=23 || exit 1
python3 compare_ring.py runs/ref23k32-30k runs/new23-30k $((30000+48)); tok ref23k32-30k new23-30k
rm -rf runs/ref23k32-30k/rank1/state-2147483647 runs/new23-30k/rank1/state-2147483647
for i in 1 2 3; do
  ./run.sh t24-$i new 4096 256 || exit 1; rm -rf runs/t24-$i/rank1/state-2147483647
  ./run.sh t23-$i new 4096 256 SPLIT=23 || exit 1; rm -rf runs/t23-$i/rank1/state-2147483647
done
echo ALL-DONE
