#!/bin/bash
# tp39: the DSpark draft on the cards, speculative decoding (OWN_SPEC=k); the text must equal the plain run
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp39; D=$S/runs/e48; bin=$S/own_run_v41_$B
while systemctl --user is-active -q dsv41-e47; do sleep 3; done
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
R1=$S/runs/ab1/base-speed-ids.txt
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
run() { # name prompt ref ntok maxseq envs...
  local name=$1 pr=$2 ref=$3 nt=$4 ms=$5; shift 5
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env "$@" OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_PROMPT=$pr OWN_EOS=-1 OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "prompt:\|spec decode\|kept guesses\|free after load\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "fault response|cat error|engine reset|coredump|gt reset" | head -3 >> $sum
}
run s5 $P1 $R1 128 4096 OWN_SPEC=5 OWN_MT_TG=2 OWN_MT_EU=6
grep -q "fault response\|engine reset" $sum && { echo STOP_FAULT >> $sum; exit 1; }
run s3 $P1 $R1 128 4096 OWN_SPEC=3 OWN_MT_TG=2 OWN_MT_EU=6
run s4 $P1 $R1 128 4096 OWN_SPEC=4 OWN_MT_TG=2 OWN_MT_EU=6
run p3ks5 $S/prompts/p3k-ids.txt $S/runs/e25/p3k-ids.txt 64 4096 OWN_SPEC=5 OWN_MT_TG=2 OWN_MT_EU=6
echo ALLDONE >> $sum
