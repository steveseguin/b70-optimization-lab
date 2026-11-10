#!/bin/bash
# tp51: (1) mix-finish bench (form 1 vs 0, bitwise + latency), card 0; (2) plain 128-token runs warm the kernel
# cache and time OWN_HC_FIN 0 / 1; (3) trace gate with HC_FIN=1 + row blocks; (4) spec, six prompts, tau 0.5 kmin 0
# + row blocks (>= 4096 rows): formats both / Q8 only, in the draft or not, HC_FIN; (5) cycle profiles
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
while systemctl --user is-active -q dsv41-e60; do sleep 3; done
B=tp51; D=$S/runs/e61; bin=$S/own_run_v41_$B
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset'
t0=$(date '+%Y-%m-%d %H:%M:%S')
$S/bench_hc_finish 0 > $D/hcfin.log 2>&1; echo "hcfin exit $?" >> $sum; cat $D/hcfin.log >> $sum
journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum
grep -q "fault response\|engine reset" $sum && { echo STOP >> $sum; exit 1; }
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1"
$S/run_exp.sh e61 $B "pl0a|OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G|speed" \
  "pl1a|OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_HC_FIN=1|speed" \
  "pl0b|OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G|speed" \
  "pl1b|OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_HC_FIN=1|speed" \
  "h16|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_HC_FIN=1 OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0|trace" \
  "h5|OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G OWN_HC_FIN=1|trace"
sed -i '/^DONE$/d' $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_GATE >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum; grep -h "spec decode\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3 >> $sum; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
for n in code prose analysis ops docs p3k; do
  if [ $n = p3k ]; then a="$P3 $R3 256 4096 -1"; else a="$PP/$n-ids.txt $R57/${n}_plain-ids.txt 512 4096 1"; fi
  s ${n}_f3d1 $a OWN_MT_TGR_FMT=3 OWN_MT_TGR_DRAFT=1
  s ${n}_f1d0 $a OWN_MT_TGR_FMT=1 OWN_MT_TGR_DRAFT=0
  s ${n}_f1d0h $a OWN_MT_TGR_FMT=1 OWN_MT_TGR_DRAFT=0 OWN_HC_FIN=1
  s ${n}_f3d0h $a OWN_MT_TGR_FMT=3 OWN_MT_TGR_DRAFT=0 OWN_HC_FIN=1
done
s p3k_prof2 $P3 $R3 128 4096 -1 OWN_MT_TGR_FMT=3 OWN_MT_TGR_DRAFT=0 OWN_HC_FIN=1 OWN_GPROF=2 OWN_GPROF_CARD=2
s p3k_prof0 $P3 $R3 128 4096 -1 OWN_MT_TGR_FMT=3 OWN_MT_TGR_DRAFT=0 OWN_HC_FIN=1 OWN_GPROF=2 OWN_GPROF_CARD=0
echo ALLDONE >> $sum
