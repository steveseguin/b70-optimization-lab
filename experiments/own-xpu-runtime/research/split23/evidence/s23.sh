#!/bin/bash
cd /dev/shm/ownrt-lab-s23
tok(){ python3 -c "
import json;a=json.load(open('runs/$1/summary.json'));b=json.load(open('runs/$2/summary.json'));print('tokens_equal $1 $2',a['tokens']==b['tokens'])"; }
P=$((4096+48))
./run.sh ref23k32 ref 4096 256 SPLIT=23 CONTEXT=32768 || exit 1
./run.sh new23k32 new 4096 256 SPLIT=23 CONTEXT=32768 || exit 1
python3 compare_ring.py runs/ref23k32 runs/new23k32 $P; tok ref23k32 new23k32
rm -rf runs/new23k32/rank1/state-2147483647
./run.sh new23 new 4096 256 SPLIT=23 || exit 1
python3 compare_ring.py runs/ref23k32 runs/new23 $P; tok ref23k32 new23
rm -rf runs/new23/rank1/state-2147483647 runs/ref23k32/rank1/state-2147483647
echo ALL-DONE
