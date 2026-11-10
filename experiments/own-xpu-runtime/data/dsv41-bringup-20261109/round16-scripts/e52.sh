#!/bin/bash
# tp42: longer answers (256 tokens at 3K, prompt 1 to its end) for acceptance; plain references; cycle profiles
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp42; D=$S/runs/e52; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
BEST="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_TGM=4:2,5:3,6:3 OWN_MT_RIDE=1"
p() { # name prompt ntok maxseq eos envs...: plain run (reference)
  local name=$1 pr=$2 nt=$3 ms=$4 eos=$5; shift 5
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $? ($(wc -l < $D/$name-ids.txt) ids)" >> $sum
  grep -h "prompt:\|decode:\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
}
s() { # name prompt ref ntok maxseq eos envs...
  local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "spec decode\|kept guesses\|kernels .* per cycle\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
}
P3=$S/prompts/p3k-ids.txt
p p3kplain $P3 256 4096 -1
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
cmp -s <(head -64 $D/p3kplain-ids.txt) $S/runs/e25/p3k-ids.txt && echo "p3kplain first 64 SAME as e25" >> $sum || echo "p3kplain first 64 DIFFER from e25" >> $sum
R3=$D/p3kplain-ids.txt
s p3ks3 $P3 $R3 256 4096 -1 OWN_SPEC=3
s p3ks4 $P3 $R3 256 4096 -1 OWN_SPEC=4
s p3ks5 $P3 $R3 256 4096 -1 OWN_SPEC=5
s p3ks2 $P3 $R3 256 4096 -1 OWN_SPEC=2
p p1plain $P1 400 4096 1
s p1s3 $P1 $D/p1plain-ids.txt 400 4096 1 OWN_SPEC=3
s p1s5 $P1 $D/p1plain-ids.txt 400 4096 1 OWN_SPEC=5
s p3ks3prof2 $P3 $R3 128 4096 -1 OWN_SPEC=3 OWN_GPROF=2 OWN_GPROF_CARD=2
s p3ks3prof0 $P3 $R3 128 4096 -1 OWN_SPEC=3 OWN_GPROF=2 OWN_GPROF_CARD=0
echo ALLDONE >> $sum
