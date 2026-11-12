#!/bin/bash
# tg101: gate for tp101 = tp100 + xperm-2 compiled in (-DOWN_R2_TAB_COPY=1: routed grid tables copied from a constant
# image). A = tp100, B = tp101, alternated. New best settings from tg100: OWN_PB=1 at prompt blocks of 256, OWN_ATT_WA=2.
# 1. traces (tp101): defaults 1 / 4 / 5 / 6 / 64 / 128 / 256, G128 at 1 / 5 / 64, PB 256, WA2 at 5, best at 5 and 256
# 2. 3K traces: default 64, best at 256   3. plain A/B with and without G128, x2 + one-token timelines
# 4. 3K reads A/B at 256 with PB   5. guessing A/B (WA2, G128), code repeated for the draft-confidence difference
#    (tg100 code_w2_2 round 66), plus the vocabulary, prose and 3K   6. check timeline (B, best)
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg101
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp101 build exit" $W/build-tp101.log 2>/dev/null; do sleep 10; done
grep -q "tp101 build exit 0" $W/build-tp101.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp101.log >> $sum
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
# ---- 1. prompt-1 traces (tp101)
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" "h4|$TM OWN_PROMPT_BLOCK=4" "h6|$TM OWN_PROMPT_BLOCK=6" \
    "h128|$TB OWN_PROMPT_BLOCK=128" "h256|$TB OWN_PROMPT_BLOCK=256" \
    "h1g|$T1 $G1" "h5g|$T5 $G1" "h64g|$TB OWN_PROMPT_BLOCK=64 $G1" "h256pb|$TB OWN_PROMPT_BLOCK=256 $PB" \
    "h5w2|$T5 $WA2" "h5best|$T5 $G1 $WA2" "h256best|$TB OWN_PROMPT_BLOCK=256 $PB $G1 $WA2")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg101 tp101 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
okn h1 h5 h64 h4 h6 h128 h256 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
okn h1g h5g h64g h256pb h5w2 h5best h256best || { echo STOP_GATE1_ARMS >> $sum; exit 1; }
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
# ---- 2. 3K traces against the tp84 reference (tp101)
for k in "b64|OWN_PROMPT_BLOCK=64" "b256best|OWN_PROMPT_BLOCK=256 $PB $G1 $WA2"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp101 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc
done
for n in b64 b256best; do grep -q "^t3k_$n TRACE_IDENTICAL" $sum && grep -q "^t3k_$n IDS40_SAME" $sum || { echo STOP_GATE2 >> $sum; exit 1; }; done
echo "gate 2: identical" >> $sum
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1), A / B alternated, warm-up first
$W/run_exp.sh tg101 tp101 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a_$rd|tp100|" "b_$rd|tp101|" "ag_$rd|tp100|$G1" "bg_$rd|tp101|$G1"; do
    IFS='|' read -r name bin envs <<< "$k"
    $W/run_exp.sh tg101 $bin "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
r tl_one_ag tp100 $P1 64 4096 -1 $D/tl_one_ag-ids.txt $PL $G1 OWN_TIMELINE=$D/tl_one_ag.txt
r tl_one_bg tp101 $P1 64 4096 -1 $D/tl_one_bg-ids.txt $PL $G1 OWN_TIMELINE=$D/tl_one_bg.txt
# ---- 4. 3K prompt reads at 256 with pb-1 (whole times, 256 answers), A / B alternated
for rd in 1 2; do
  for k in "p3k_a_$rd|tp100|$G1" "p3k_b_$rd|tp101|$G1"; do
    IFS='|' read -r name bin envs <<< "$k"
    r $name $bin $p 256 4096 -1 $D/$name-ids.txt $PL OWN_PROMPT_BLOCK=256 $PB $envs
    same $D/$name-ids.txt $W/runs/e52/p3kplain-ids.txt 256 $name
  done
done
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
for rd in 1 2 3; do
  for b in a b; do
    bin=tp100; [ $b = b ] && bin=tp101
    sp code_${b}_$rd $bin code $BEST $WA2 $G1; glog $D/code_${b}_$rd-spec.txt $T100/code_w2_1-spec.txt code_${b}_${rd}_vs_w2_1
    if [ $rd -le 2 ]; then
      sp analysis_${b}_$rd $bin analysis $BEST $WA2 $G1; glog $D/analysis_${b}_$rd-spec.txt $T100/analysis_w2_1-spec.txt analysis_${b}_${rd}_vs_w2_1
    fi
  done
done
for b in a b; do
  bin=tp100; [ $b = b ] && bin=tp101
  sp code_${b}voc $bin code $BEST $WA2 $G1 $VOC
  sp analysis_${b}voc $bin analysis $BEST $WA2 $G1 $VOC
  sp prose_${b} $bin prose $BEST $WA2 $G1
  r p3k_spec_${b} $bin $p 256 4096 -1 $D/p3k_spec_${b}-ids.txt $BEST $WA2 $G1 OWN_SPEC_LOG=$D/p3k_spec_${b}-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. check timeline with the best (B)
r tl_ck tp101 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $WA2 $G1 OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
