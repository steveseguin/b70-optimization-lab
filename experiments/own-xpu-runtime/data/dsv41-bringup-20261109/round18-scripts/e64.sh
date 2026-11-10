#!/bin/bash
# tp53 (ahead of time): layer 0's Q2_K expert down rows through RoutedQ2KF (OWN_Q2K_FAST, default on; bitwise in
# bench_routed_m1 ONLY=q2k). (1) trace gates; (2) plain 128-token answers, fast Q2_K off vs on, interleaved;
# (3) six prompts, off vs on; (4) cycle profile on card 2; (5) prompt-reading profile on card 2 (3K prompt, 2 answer tokens)
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp53; D=$S/runs/e64; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
$S/run_exp.sh e64 $B "h16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0|trace" \
  "h5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G|trace" \
  "h1|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G|trace" \
  "p0a|$PL OWN_Q2K_FAST=0|speed" \
  "p1a|$PL|speed" \
  "p0b|$PL OWN_Q2K_FAST=0|speed" \
  "p1b|$PL|speed"
sed -i '/^DONE$/d' $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_GATE >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "spec decode\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
for n in code prose analysis ops docs p3k; do
  if [ $n = p3k ]; then a="$P3 $R3 256 4096 -1"; else a="$PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1"; fi
  s ${n}_q0 $a OWN_Q2K_FAST=0
  s ${n}_q1 $a
done
s p3k_prof $P3 $R3 128 4096 -1 OWN_GPROF=2 OWN_GPROF_CARD=2
t0=$(date '+%Y-%m-%d %H:%M:%S')
env $PL OWN_PROMPT=$P3 OWN_EOS=-1 OWN_GPROF=2 OWN_GPROF_CARD=2 $bin - 2 $D/prompt_prof-ids.txt 4096 > $D/prompt_prof.log 2>&1
echo "prompt_prof exit $?" >> $sum; grep -h "prompt:\|rror\|timed out" $D/prompt_prof.log | sed "s/^/prompt_prof: /" >> $sum
journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
echo ALLDONE >> $sum
