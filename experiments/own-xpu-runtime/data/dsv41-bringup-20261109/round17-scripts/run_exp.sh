#!/bin/bash
# run_exp.sh RUN BIN then lines of "name|ENV=.. ENV=..|speed or gprof" on stdin-like args
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/$1; bin=$S/own_run_v41_$2; shift 2
B=$S/runs/ab1
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
sum=$D/summary.txt
for spec in "$@"; do
  IFS='|' read -r name envs mode <<< "$spec"
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  if [ "$mode" = trace ]; then
    env $envs OWN_PROMPT=$P OWN_TRACE=$D/$name.trc OWN_TRACE_STEPS=3 $bin - 40 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
    echo "$name exit $?" >> $sum
    cmp -s $D/$name.trc $B/base.trc && echo "$name TRACE_IDENTICAL" >> $sum || echo "$name TRACE_DIFFERS" >> $sum
    cmp -s $D/$name-ids.txt $B/base-ids.txt && echo "$name IDS40_SAME" >> $sum || echo "$name IDS40_DIFFER" >> $sum
  elif [ "$mode" = gprof ]; then
    env $envs OWN_PROMPT=$P OWN_EOS=-1 $bin - 48 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
    echo "$name exit $?" >> $sum
  else
    env $envs OWN_PROMPT=$P OWN_EOS=-1 $bin - 128 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
    echo "$name exit $?" >> $sum
    cmp -s $D/$name-ids.txt $B/base-speed-ids.txt && echo "$name SPEED128_SAME" >> $sum || echo "$name SPEED128_DIFFER" >> $sum
  fi
  grep -h "decode:\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "fault response|cat error|engine reset|coredump has been created|gt reset" | head -3 >> $sum
done
echo DONE >> $sum
