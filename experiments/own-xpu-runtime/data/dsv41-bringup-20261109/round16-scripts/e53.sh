#!/bin/bash
# tp43: small row launches one sub-group per work-group (OWN_MT_RWG), runner stops at a kept end of sentence
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp43; D=$S/runs/e53; bin=$S/own_run_v41_$B
mkdir -p $D
$S/run_exp.sh e53 $B "grwg16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128|trace" \
  "grwg5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=5:3,4:2,3:1,2:1 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128|trace"
sed -i '/^DONE$/d' $D/summary.txt
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $D/summary.txt && { echo STOP_GATE >> $D/summary.txt; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
R1=$S/runs/ab1/base-speed-ids.txt
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
BEST="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_TGM=2:1,3:1,4:2,5:3,6:3 OWN_MT_RIDE=1"
v() { # name k envs...
  local name=$1 k=$2; shift 2
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$P1 OWN_EOS=-1 OWN_VERIFY_REF=$R1 OWN_VERIFY_TEST=$k OWN_VERIFY_BAD=0 $bin - 128 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "verify test\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
}
s() { # name prompt ref ntok maxseq eos envs...
  local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
}
v v3r0 3
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
v v3r128 3 OWN_MT_RWG=128
v v3r32 3 OWN_MT_RWG=32
v v2r128 2 OWN_MT_RWG=128
v v5r128 5 OWN_MT_RWG=128
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
s p3ks3 $P3 $R3 256 4096 -1 OWN_SPEC=3 OWN_MT_RWG=128
s p3ks2 $P3 $R3 256 4096 -1 OWN_SPEC=2 OWN_MT_RWG=128
s p3ks4 $P3 $R3 256 4096 -1 OWN_SPEC=4 OWN_MT_RWG=128
s p1s3 $P1 $S/runs/e52/p1plain-ids.txt 400 4096 1 OWN_SPEC=3 OWN_MT_RWG=128
echo ALLDONE >> $sum
