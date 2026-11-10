#!/bin/bash
# tp45: the draft head only for the guesses used (draft_tp nrows); group sizes 3:3, 4:4 with the fused route
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
while systemctl --user is-active -q dsv41-e55; do sleep 3; done
B=tp45; D=$S/runs/e56; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
R1=$S/runs/ab1/base-speed-ids.txt
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
BASE="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1"
T1="OWN_MT_TGM=2:1,3:1,4:2,5:3,6:3"
v() { local name=$1 k=$2; shift 2; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BASE "$@" OWN_PROMPT=$P1 OWN_EOS=-1 OWN_VERIFY_REF=$R1 OWN_VERIFY_TEST=$k OWN_VERIFY_BAD=0 $bin - 128 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "verify test\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BASE "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "prompt:\|spec decode\|kept guesses\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
v v2g1 2 $T1
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
v v2g3 2 OWN_MT_TGM=3:3
v v3g4 3 OWN_MT_TGM=4:4
v v3g2 3 $T1
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
s p3ks3 $P3 $R3 256 4096 -1 OWN_SPEC=3 $T1
s p3ks4 $P3 $R3 256 4096 -1 OWN_SPEC=4 $T1
s p3ks2 $P3 $R3 256 4096 -1 OWN_SPEC=2 $T1
echo ALLDONE >> $sum
