#!/bin/bash
# tp46: five varied prompts (code, prose, analysis, ops, docs): plain reference to the end (max 512), spec k=3 and
# k=5 with the draft's per-guess probabilities logged (OWN_SPEC_LOG); 3K k=5 logged
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
while systemctl --user is-active -q dsv41-e56; do sleep 3; done
B=tp46; D=$S/runs/e57; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
BASE="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_MT_TGM=2:1,3:1,4:2,5:3,6:3"
p() { local name=$1 pr=$2 nt=$3 ms=$4 eos=$5; shift 5; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BASE "$@" OWN_PROMPT=$pr OWN_EOS=$eos $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $? ($(wc -l < $D/$name-ids.txt) ids)" >> $sum
  grep -h "decode:\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BASE "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "spec decode\|kept guesses\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
first=1
for n in code prose analysis ops docs; do
  p ${n}_plain $PP/$n-ids.txt 512 4096 1
  [ $first = 1 ] && { grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }; first=0; }
  s ${n}_s5 $PP/$n-ids.txt $D/${n}_plain-ids.txt 512 4096 1 OWN_SPEC=5 OWN_SPEC_LOG=$D/${n}_s5.conf
  s ${n}_s3 $PP/$n-ids.txt $D/${n}_plain-ids.txt 512 4096 1 OWN_SPEC=3
done
s p3k_s5 $S/prompts/p3k-ids.txt $S/runs/e52/p3kplain-ids.txt 256 4096 -1 OWN_SPEC=5 OWN_SPEC_LOG=$D/p3k_s5.conf
echo ALLDONE >> $sum
