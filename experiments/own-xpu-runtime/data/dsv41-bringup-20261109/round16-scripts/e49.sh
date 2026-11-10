#!/bin/bash
# tp40: commit work moved onto the card threads (commit_pending), draft rows staged by the checking step.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp40; D=$S/runs/e49; bin=$S/own_run_v41_$B
mkdir -p $D
$S/run_exp.sh e49 $B "g16tg2eu|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=2 OWN_MT_TG_MAX=16 OWN_MT_EU=6|trace"
sed -i '/^DONE$/d' $D/summary.txt
grep -q "TRACE_DIFFERS\|exit [^0]" $D/summary.txt && { echo STOP_GATE >> $D/summary.txt; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
run() { # name prompt ref ntok maxseq envs...
  local name=$1 pr=$2 ref=$3 nt=$4 ms=$5; shift 5
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  env "$@" OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_PROMPT=$pr OWN_EOS=-1 OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -h "prompt:\|spec decode\|kept guesses\|kernels .* per cycle\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "fault response|cat error|engine reset|coredump|gt reset" | head -3 >> $sum
}
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e25/p3k-ids.txt
run p3ks5 $P3 $R3 64 4096 OWN_SPEC=5 OWN_MT_TG=2 OWN_MT_EU=6
grep -q "fault response\|engine reset\|DIFFERENT" $sum && { echo STOP >> $sum; exit 1; }
run p3ks4 $P3 $R3 64 4096 OWN_SPEC=4 OWN_MT_TG=2 OWN_MT_EU=6
run p3ks3 $P3 $R3 64 4096 OWN_SPEC=3 OWN_MT_TG=2 OWN_MT_EU=6
run p3ks5prof $P3 $R3 64 4096 OWN_SPEC=5 OWN_MT_TG=2 OWN_MT_EU=6 OWN_GPROF=2 OWN_GPROF_CARD=2
run p10ks5 $S/prompts/p10k-ids.txt $S/runs/e25/p10k-ids.txt 64 12288 OWN_SPEC=5 OWN_MT_TG=2 OWN_MT_EU=6
echo ALLDONE >> $sum
