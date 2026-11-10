#!/bin/bash
# tp43 profiles, card 2: plain one-token decode vs a checked block of 4 (all kept), same settings
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp43; D=$S/runs/e54; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
R1=$S/runs/ab1/base-speed-ids.txt
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
BEST="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_TGM=2:1,3:1,4:2,5:3,6:3 OWN_MT_RIDE=1 OWN_MT_RWG=128"
for c in 2 0; do
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST OWN_PROMPT=$P1 OWN_EOS=-1 OWN_GPROF=2 OWN_GPROF_CARD=$c $bin - 64 $D/plain$c-ids.txt 4096 > $D/plain$c.log 2>&1
  echo "plain$c exit $?" >> $sum; grep -h "decode:\|kernels \|rror" $D/plain$c.log | sed "s/^/plain$c: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST OWN_PROMPT=$P1 OWN_EOS=-1 OWN_VERIFY_REF=$R1 OWN_VERIFY_TEST=3 OWN_VERIFY_BAD=0 OWN_GPROF=2 OWN_GPROF_CARD=$c $bin - 128 $D/v3_$c-ids.txt 4096 > $D/v3_$c.log 2>&1
  echo "v3_$c exit $?" >> $sum; grep -h "verify test\|kernels \|rror" $D/v3_$c.log | sed "s/^/v3_$c: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
done
echo ALLDONE >> $sum
