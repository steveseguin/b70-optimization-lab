#!/bin/bash
# tp49: (1) gates: traces with the row-blocked dense rows forced on every matrix (OWN_MT_TGR_ROWS=0) after blocks of
# 16 / 5 / 7 and a control; verify test k=3 with them; the unrolled draft experts give the same guesses and
# probabilities as the old kernel (OWN_DR_MXN=0 vs 1, logs compared); zero-guess rounds (OWN_SPEC_KMIN=0).
# (2) speed, six prompts: tau 0.5 kmin 1 / kmin 0 / kmin 0 + row blocks (OWN_MT_TGR, matrices >= 4096 rows)
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp49; D=$S/runs/e60; bin=$S/own_run_v41_$B
mkdir -p $D
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1"
$S/run_exp.sh e60 $B "g16c|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G|trace" \
  "g16r2|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:2,1:2 OWN_MT_TGR_ROWS=0|trace" \
  "g5r4|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 OWN_MT_TGR=1:4,2:4,3:4,4:4,5:4 OWN_MT_TGR_ROWS=0 $G|trace" \
  "g7r2|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=7 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_TGM=6:3,5:3 OWN_MT_TGR=7:2,6:4,5:2,4:2,3:2,2:2,1:2 OWN_MT_TGR_ROWS=0 $G|trace"
sed -i '/^DONE$/d' $D/summary.txt
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $D/summary.txt && { echo STOP_GATE >> $D/summary.txt; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
R1=$S/runs/ab1/base-speed-ids.txt
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
BEST="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3"
RB="OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
v() { local name=$1 k=$2; shift 2; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$P1 OWN_EOS=-1 OWN_VERIFY_REF=$R1 OWN_VERIFY_TEST=$k OWN_VERIFY_BAD=0 $bin - 128 $D/$name-ids.txt 4096 > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "verify test\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "spec decode\|kept guesses\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
v v3r4 3 OWN_MT_TGR=4:4,2:4,1:4 OWN_MT_TGR_ROWS=0
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
s code_mx0 $PP/code-ids.txt $R57/code_plain-ids.txt 512 4096 1 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_DR_MXN=0 OWN_SPEC_LOG=$D/code_mx0.conf
s code_mx1 $PP/code-ids.txt $R57/code_plain-ids.txt 512 4096 1 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_DR_MXN=1 OWN_SPEC_LOG=$D/code_mx1.conf
cmp -s $D/code_mx0.conf $D/code_mx1.conf && echo "DRAFT_MXN_SAME_GUESSES" >> $sum || echo "DRAFT_MXN_DIFFERENT" >> $sum
for n in code prose analysis ops docs; do
  s ${n}_k1 $PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1 OWN_SPEC=5 OWN_SPEC_TAU=0.5
  s ${n}_k0 $PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0
  s ${n}_k0r $PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 $RB
done
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
s p3k_k1 $P3 $R3 256 4096 -1 OWN_SPEC=5 OWN_SPEC_TAU=0.5
s p3k_k0 $P3 $R3 256 4096 -1 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0
s p3k_k0r $P3 $R3 256 4096 -1 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 $RB
echo ALLDONE >> $sum
