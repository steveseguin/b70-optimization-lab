#!/bin/bash
# Usage: run27.sh LAUNCH.json OUTDIR [PROMPT]   (one rank-1 batched prefill run on spare card 27)
set -u
LAUNCH=$1; OUT=$2; PROMPT=${3:-4096}
DRV=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
LOG=$OUT.runlog
busy() { for p in $(pgrep -x sc117-engine); do ls -l /proc/$p/fd 2>/dev/null | grep -q renderD131 && return 0; done; return 1; }
echo "wait-start $(date +%s)" >> $LOG
exec 9>/dev/shm/card27.lock
flock 9
while busy; do sleep 60; done
START=$(date +%s); echo "start $START" >> $LOG
python3 -B $DRV run --launch $LAUNCH --out $OUT --steps 4 --prompt $PROMPT --batched --rows 32 --cache /dev/shm/ownrt-lab-experts/cache >> $LOG 2>&1 &
DP=$!
# verify the engine holds only renderD131 (poll during load)
for i in $(seq 1 60); do
  sleep 2
  for p in $(pgrep -x sc117-engine); do
    if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- "$OUT/rank1"; then
      nodes=$(ls -l /proc/$p/fd 2>/dev/null | grep -o 'renderD[0-9]*' | sort -u | tr '\n' ' ')
      echo "pid $p nodes [$nodes] t=$((i*2))" >> $LOG
    fi
  done
  grep -q "renderD" $LOG && [ $i -ge 15 ] && break
done
wait $DP; RC=$?
END=$(date +%s); echo "end $END rc $RC" >> $LOG
journalctl -k --since "@$START" --no-pager 2>/dev/null | grep -iE "xe .*(fault|reset|error|timed out)|CAT error|GuC" > $OUT.kfaults
echo "kfaults $(wc -l < $OUT.kfaults)" >> $LOG
flock -u 9
