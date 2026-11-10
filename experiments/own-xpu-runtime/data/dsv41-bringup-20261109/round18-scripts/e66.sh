#!/bin/bash
# tp56 (ahead of time): (a) the vocabulary head's 2-6 token blocks in their own token groups with no row blocks
# (OWN_MT_TGW_ROWS=16384 + OWN_MT_TGWM 2:2,3:3,4:2,5:3,6:3, default on; bitwise in bench_q6k_rows: rowg<G> vs rowg<1>); (b) uneven row shares (OWN_TP_WEIGHTS): cards 2 and 5
# hold two attention groups each, so they take fewer expert / shared / output-b / engram rows (default equal).
# (1) trace gates, also with weights; (2) plain 128-token answers; (3) six prompts: base (head off, equal) - head -
# head + weights 875 - head + weights 750 - base again (A ... A for the order effect); (4) cycle profiles card 2 / 0
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
B=tp56; D=$S/runs/e66; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
W8="OWN_TP_WEIGHTS=1000,1000,875,1000,1000,875"
W7="OWN_TP_WEIGHTS=1000,1000,750,1000,1000,750"
$S/run_exp.sh e66 $B "h16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0|trace" \
  "h5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G|trace" \
  "h1|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G|trace" \
  "h16w7|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0 $W7|trace" \
  "h1w7|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G $W7|trace" \
  "p1|$PL|speed" \
  "p1w8|$PL $W8|speed" \
  "p1w7|$PL $W7|speed" \
  "p1r|$PL|speed"
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
  s ${n}_base $a OWN_MT_TGW_ROWS=0
  s ${n}_head $a
  s ${n}_w8 $a $W8
  s ${n}_w7 $a $W7
  s ${n}_baser $a OWN_MT_TGW_ROWS=0
done
s p3k_prof2 $P3 $R3 128 4096 -1 $W8 OWN_GPROF=2 OWN_GPROF_CARD=2
s p3k_prof0 $P3 $R3 128 4096 -1 $W8 OWN_GPROF=2 OWN_GPROF_CARD=0
echo ALLDONE >> $sum
