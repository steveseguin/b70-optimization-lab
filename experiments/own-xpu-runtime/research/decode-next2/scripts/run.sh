#!/bin/bash
# Usage: run.sh LAUNCH.json OUTNAME PROMPT STEPS -- one rank-1 engine run on card 27 under the shared lock.
# Fault check BEFORE (any xe fault on any card since watch-from) and AFTER (since run start); any match -> HALT.
set -u
LAUNCH=$1; NAME=$2; PROMPT=${3:-4096}; STEPS=${4:-48}
O=/dev/shm/ownrt-lab-dn2; OUT=$O/runs/$NAME; LOG=$O/runs/$NAME.runlog
PAT='xe .*(fault|reset|error|timed out)|CAT error|GuC'
[ -e $O/HALT ] && { echo "HALT present" >> $LOG; exit 3; }
DRV=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
echo "wait-start $(date +%s)" >> $LOG
exec 9>/dev/shm/card27.lock
flock 9
[ -e $O/HALT ] && { echo "HALT present" >> $LOG; flock -u 9; exit 3; }
PRE=$(journalctl -k --since "@$(cat $O/watch-from)" --no-pager 2>/dev/null | grep -iE "$PAT")
if [ -n "$PRE" ]; then echo "PRE-FAULT: $PRE" >> $LOG; echo "pre-run fault seen before $NAME" > $O/HALT; flock -u 9; exit 4; fi
START=$(date +%s); echo "start $START" >> $LOG
nice -n 10 taskset -c 8-15,24-31 python3 -B $DRV run --launch $LAUNCH --out $OUT --steps $STEPS --prompt $PROMPT --batched --rows 256 --cache $O/cache >> $LOG 2>&1 &
DP=$!
for i in $(seq 1 60); do
  sleep 2
  for p in $(pgrep -x sc117-engine); do
    if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q -- "$OUT/rank1"; then
      nodes=$(ls -l /proc/$p/fd 2>/dev/null | grep -o 'renderD[0-9]*' | sort -u | tr '\n' ' ')
      [ -n "$nodes" ] && echo "pid $p nodes [$nodes] t=$((i*2))" >> $LOG
    fi
  done
  [ $i -ge 12 ] && grep -q "renderD" $LOG && break
done
wait $DP; RC=$?
END=$(date +%s); echo "end $END rc $RC" >> $LOG
sleep 2
journalctl -k --since "@$START" --no-pager 2>/dev/null | grep -iE "$PAT" > $OUT.kfaults
NF=$(wc -l < $OUT.kfaults); echo "kfaults $NF" >> $LOG
if [ "$NF" != "0" ]; then echo "FAULT in $NAME" > $O/HALT; fi
grep "nodes" $LOG | grep -v "\[renderD131 \]" > /dev/null && { echo "FOREIGN NODE in $NAME" >> $LOG; echo "foreign node $NAME" > $O/HALT; }
rm -f $OUT/rank1/state-2147483647/state.bundle
flock -u 9
exit $RC
