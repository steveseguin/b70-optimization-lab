#!/bin/bash
# tp41: unpacked rows in token groups (OWN_MT_TGU), mix dots riding in q_a / router (OWN_MT_RIDE), G=3 groups
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp41; D=$S/runs/e50; bin=$S/own_run_v41_$B
mkdir -p $D
$S/run_exp.sh e50 $B "gride|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=2 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1|trace" \
  "gtg3|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=7 OWN_MT_TG=3 OWN_MT_TG_MAX=16 OWN_MT_EU=6 OWN_MT_TGU=3|trace" \
  "gtgu1|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_TGU=1 OWN_MT_RIDE=1|trace"
sed -i '/^DONE$/d' $D/summary.txt
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $D/summary.txt && { echo STOP_GATE >> $D/summary.txt; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
R1=$S/runs/ab1/base-speed-ids.txt
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
v() { # name envs...: checking 5 correct guesses per cycle (6 tokens per check)
  local name=$1; shift
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env "$@" OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_PROMPT=$P1 OWN_EOS=-1 OWN_VERIFY_REF=$R1 OWN_VERIFY_TEST=5 OWN_VERIFY_BAD=0 $bin - 128 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "verify test\|kernels .* per cycle\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "fault response|cat error|engine reset|coredump|gt reset" | head -3 >> $sum
}
s() { # name prompt ref ntok maxseq envs...
  local name=$1 pr=$2 ref=$3 nt=$4 ms=$5; shift 5
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env "$@" OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_PROMPT=$pr OWN_EOS=-1 OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "prompt:\|spec decode\|kept guesses\|kernels .* per cycle\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "fault response|cat error|engine reset|coredump|gt reset" | head -3 >> $sum
}
v v_base OWN_MT_TG=2 OWN_MT_EU=6
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
v v_tgu2 OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_TGU=2
v v_ride OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_RIDE=1
v v_both OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1
v v_tg3 OWN_MT_TG=3 OWN_MT_EU=6 OWN_MT_TGU=3 OWN_MT_RIDE=1
v v_tgu1 OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_TGU=1 OWN_MT_RIDE=1
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e25/p3k-ids.txt
s p3ks3 $P3 $R3 64 4096 OWN_SPEC=3 OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1
s p3ks5 $P3 $R3 64 4096 OWN_SPEC=5 OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1
s p3ks4 $P3 $R3 64 4096 OWN_SPEC=4 OWN_MT_TG=2 OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1
echo ALLDONE >> $sum
