#!/bin/bash
# tg102: gate for tp102 = tp101 + the draft head's per-card slots padded to 128 B + pace-1 (OWN_MT_PACE=1: the 16-head
# cards' q_b / output-a rows in checks of 2-6 tokens in persistent pipelined launches) + pb-1 (OWN_PB) and wa-2
# (OWN_ATT_WA=2) as defaults (OWN_PB=0 / OWN_ATT_WA=0 switch them off). A = tp101, B = tp102.
# 1. traces: defaults 1 / 4 / 5 / 6 / 64 / 128 / 256, both off at 5 / 256, PACE at 2-6, each role alone at 5, PACE + G128
# 2. 3K traces: default 64 / 256, best 256   3. plain B x2 (+ G128)   4. 3K reads at 256: A (PB on) / B default
# 5. guessing A (WA2 G128) / B (defaults G128 PACE) x2 + B without PACE; prose, 3K   6. check timeline (B best)
# + px-1 (OWN_PX=1: prompt blocks of 256 as two halves, exchanges on a second queue per card): prompt-1 trace at 256,
#   3K traces at 256 (plain, OWN_PX_CHECK=1, OWN_PX_SERIAL=1) and 128 (OWN_PX_MIN=64); 3K reads B vs B+PX x2.
#   A PX difference skips the PX speed arms only (PXOK=0), never stops the gate.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg102
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp102 build exit" $W/build-tp102.log 2>/dev/null; do sleep 10; done
grep -q "tp102 build exit 0" $W/build-tp102.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp102.log >> $sum
SP=
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
tg=$(date '+%Y-%m-%d %H:%M:%S')
echo "start $tg" >> $sum
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
TM="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 $G"
G1="OWN_PAIR_G128=1"; WA2="OWN_ATT_WA=2"; PB="OWN_PB=1"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
# ---- 1. prompt-1 traces (tp102)
PC="OWN_MT_PACE=1"; OFF="OWN_PB=0 OWN_ATT_WA=0"
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" "h4|$TM OWN_PROMPT_BLOCK=4" "h6|$TM OWN_PROMPT_BLOCK=6" \
    "h128|$TB OWN_PROMPT_BLOCK=128" "h256|$TB OWN_PROMPT_BLOCK=256" "h5off|$T5 $OFF" "h256off|$TB OWN_PROMPT_BLOCK=256 $OFF" \
    "h2pc|$TM OWN_PROMPT_BLOCK=2 $PC" "h3pc|$TM OWN_PROMPT_BLOCK=3 $PC" "h4pc|$TM OWN_PROMPT_BLOCK=4 $PC" \
    "h5pc|$T5 $PC" "h6pc|$TM OWN_PROMPT_BLOCK=6 $PC" "h5pc1|$T5 $PC OWN_MT_PACE_ROLES=1" \
    "h5pc2|$T5 $PC OWN_MT_PACE_ROLES=2" "h5pc4|$T5 $PC OWN_MT_PACE_ROLES=4" "h5best|$T5 $PC $G1" "h4best|$TM OWN_PROMPT_BLOCK=4 $PC $G1")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg102 tp102 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
okn h1 h5 h64 h4 h6 h128 h256 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
okn h5off h256off h2pc h3pc h4pc h5pc h6pc h5pc1 h5pc2 h5pc4 h5best h4best || { echo STOP_GATE1_ARMS >> $sum; exit 1; }
echo "gate 1: all identical" >> $sum
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|lookup guesses\|host io\|rows per card\|heads per card\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference (tp102)
for k in "b64|OWN_PROMPT_BLOCK=64" "b256|OWN_PROMPT_BLOCK=256" "b256best|OWN_PROMPT_BLOCK=256 $PC $G1"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp102 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc
done
for n in b64 b256 b256best; do grep -q "^t3k_$n TRACE_IDENTICAL" $sum && grep -q "^t3k_$n IDS40_SAME" $sum || { echo STOP_GATE2 >> $sum; exit 1; }; done
echo "gate 2: identical" >> $sum
PX="OWN_PX=1"
$W/run_exp.sh tg102 tp102 "h256px|$TB OWN_PROMPT_BLOCK=256 $PX|trace"; sed -i '/^DONE$/d' $sum; fcheck "$tg"
$W/run_exp.sh tg102 tp102 "h64px|$TB OWN_PROMPT_BLOCK=64 $PX OWN_PX_MIN=32|trace"; sed -i '/^DONE$/d' $sum; fcheck "$tg"
for k in "b256px|OWN_PROMPT_BLOCK=256 $PX" "b256pxck|OWN_PROMPT_BLOCK=256 $PX OWN_PX_CHECK=1" \
         "b256pxser|OWN_PROMPT_BLOCK=256 $PX OWN_PX_SERIAL=1" "b128px|OWN_PROMPT_BLOCK=128 $PX OWN_PX_MIN=64" \
         "b250px|OWN_PROMPT_BLOCK=250 $PX OWN_PX_MIN=64 OWN_PX_CHECK=1" \
         "b256pxw|OWN_PROMPT_BLOCK=256 $PX OWN_PX_WG=64 OWN_PX_GRF=128,128,128,128,128,128,128,128"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp102 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc
done
PXOK=1; okn h256px h64px || PXOK=0
for n in b256px b256pxck b256pxser b128px b250px b256pxw; do grep -q "^t3k_$n TRACE_IDENTICAL" $sum && grep -q "^t3k_$n IDS40_SAME" $sum || PXOK=0; done
echo "gate 2px: PXOK=$PXOK" >> $sum
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1), warm-up first
$W/run_exp.sh tg102 tp102 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "b_$rd|tp102|" "bg_$rd|tp102|$G1"; do
    IFS='|' read -r name bin envs <<< "$k"
    $W/run_exp.sh tg102 $bin "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. 3K prompt reads at 256 with pb-1 (whole times, 256 answers), A / B alternated
for rd in 1 2; do
  for k in "p3k_a_$rd|tp101|$PB $G1" "p3k_b_$rd|tp102|$G1" "p3k_px_$rd|tp102|$G1 $PX"; do
    IFS='|' read -r name bin envs <<< "$k"
    case $name in p3k_px*) [ $PXOK = 1 ] || continue;; esac
    r $name $bin $p 256 4096 -1 $D/$name-ids.txt $PL OWN_PROMPT_BLOCK=256 $envs
    same $D/$name-ids.txt $W/runs/e52/p3kplain-ids.txt 256 $name
  done
done
if [ $PXOK = 1 ]; then
  r p3k_pxser tp102 $p 256 4096 -1 $D/p3k_pxser-ids.txt $PL OWN_PROMPT_BLOCK=256 $G1 $PX OWN_PX_SERIAL=1
  same $D/p3k_pxser-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_pxser
fi
# ---- 5. guessing (prompt blocks of 64), A / B alternated with WA2 + G128; code repeated 3x per binary
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 b=$2 n=$3; shift 3
  r $name $b $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
T100=$W/runs/tg100
for rd in 1 2; do
  for b in a b; do
    if [ $b = a ]; then bin=tp101; e="$WA2 $G1"; else bin=tp102; e="$G1 $PC"; fi
    sp code_${b}_$rd $bin code $BEST $e; glog $D/code_${b}_$rd-spec.txt $T100/code_w2_1-spec.txt code_${b}_${rd}_vs_w2_1
    sp analysis_${b}_$rd $bin analysis $BEST $e; glog $D/analysis_${b}_$rd-spec.txt $T100/analysis_w2_1-spec.txt analysis_${b}_${rd}_vs_w2_1
  done
done
sp code_bnp tp102 code $BEST $G1; glog $D/code_bnp-spec.txt $T100/code_w2_1-spec.txt code_bnp_vs_w2_1
sp analysis_bnp tp102 analysis $BEST $G1; glog $D/analysis_bnp-spec.txt $T100/analysis_w2_1-spec.txt analysis_bnp_vs_w2_1
for b in a b; do
  if [ $b = a ]; then bin=tp101; e="$WA2 $G1"; else bin=tp102; e="$G1 $PC"; fi
  sp prose_${b} $bin prose $BEST $e
  r p3k_spec_${b} $bin $p 256 4096 -1 $D/p3k_spec_${b}-ids.txt $BEST $e OWN_SPEC_LOG=$D/p3k_spec_${b}-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
sp code_bvoc tp102 code $BEST $G1 $PC $VOC
r p3k_spec_b256 tp102 $p 256 4096 -1 $D/p3k_spec_b256-ids.txt $BEST $G1 $PC OWN_PROMPT_BLOCK=256 OWN_SPEC_LOG=$D/p3k_spec_b256-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
if [ $PXOK = 1 ]; then
  r p3k_spec_b256px tp102 $p 256 4096 -1 $D/p3k_spec_b256px-ids.txt $BEST $G1 $PC OWN_PROMPT_BLOCK=256 $PX OWN_SPEC_LOG=$D/p3k_spec_b256px-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
  glog $D/p3k_spec_b256px-spec.txt $D/p3k_spec_b256-spec.txt p3k_spec_b256px_vs_b256
fi
sp analysis_bvoc tp102 analysis $BEST $G1 $PC $VOC
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. check timeline with the best (B)
r tl_ck tp102 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $G1 $PC OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
