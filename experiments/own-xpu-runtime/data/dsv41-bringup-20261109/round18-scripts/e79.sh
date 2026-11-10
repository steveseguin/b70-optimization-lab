#!/bin/bash
# tp66 = tp65 + OWN_TP_HEADS (attention heads per card in units of 4; a group of 8 heads split between two
# neighbours swaps its head outputs, XchgPair) + OWN_TP_HEADS_DR (the draft's stages too). Default (unset) =
# tp65's layout. No CPU builds during this campaign; stops at the first fault line.
# A = 3,3,3,3,2,2 (cards 4, 5 light; pairs 0-1, 2-3), B = 2,3,3,3,3,2 (cards 0, 5 light; pairs 1-2, 3-4).
# (0) gates: traces of blocks of 16 / 5 / one token with A, block 16 with B and default, plain 128 with A + DR;
# (1) plain 128: default, A, A with pull exchanges from 6 KB (one-token output-a slices are 6 KB in A), twice;
# (2) six prompts x [n default, a A, ad A + draft, bd B + draft], two rounds (second reversed); a draft that
#     computes the same values keeps the same guesses: the cycle / kept counts must equal n's.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
D=$S/runs/e79
mkdir -p $D
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
sum=$D/summary.txt; marks=$D/marks.txt
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.01 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
HA="OWN_TP_HEADS=3,3,3,3,2,2"; HB="OWN_TP_HEADS=2,3,3,3,3,2"
tg=$(date '+%Y-%m-%d %H:%M:%S')
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
$S/run_exp.sh e79 tp66 "h16a|$T16 $HA|trace" "h5a|$T5 $HA|trace" "h1a|$T1 $HA|trace" "h16b|$T16 $HB|trace" \
  "h16n|$T16|trace" "p1ad0|$PL $HA OWN_TP_HEADS_DR=1|speed"
$S/run_exp.sh e79 tp66 "p1n1|$PL|speed" "p1a1|$PL $HA|speed" "p1x1|$PL $HA OWN_XPULL_MIN=6144|speed"
$S/run_exp.sh e79 tp66 "p1x2|$PL $HA OWN_XPULL_MIN=6144|speed" "p1a2|$PL $HA|speed" "p1n2|$PL|speed"
sed -i '/^DONE$/d' $sum
journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3 | sed 's/^/FAULT: /' >> $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]\|FAULT" $sum && { echo STOP_GATE >> $sum; exit 1; }
PP=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
R57=$S/runs/e57
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
bin=$S/own_run_v41_tp66
s() { local name=$1 pr=$2 ref=$3 nt=$4 ms=$5 eos=$6; shift 6; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env $BEST "$@" OWN_PROMPT=$pr OWN_EOS=$eos OWN_VERIFY_REF=$ref OWN_DSPARK=$DS $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum; grep -h "prompt:\|spec decode\|host io\|rror\|timed out" $D/$name.log | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
P3=$S/prompts/p3k-ids.txt; R3=$S/runs/e52/p3kplain-ids.txt
args() { if [ $1 = p3k ]; then echo "$P3 $R3 256 4096 -1"; else echo "$PP/$1-ids.txt $R57/${1}_plain-ids.txt 512 4096 1"; fi; }
declare -A A
A[n]=""
A[a]="$HA"
A[ad]="$HA OWN_TP_HEADS_DR=1"
A[bd]="$HB OWN_TP_HEADS_DR=1"
for n in code prose analysis ops docs p3k; do for a in n a ad bd; do s ${n}_${a}1 $(args $n) ${A[$a]}; done; done
for n in code prose analysis ops docs p3k; do for a in bd ad a n; do s ${n}_${a}2 $(args $n) ${A[$a]}; done; done
echo ALLDONE >> $sum
