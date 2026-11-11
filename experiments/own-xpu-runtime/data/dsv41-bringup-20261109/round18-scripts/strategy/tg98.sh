#!/bin/bash
# tg98: gate for tp98 = tp97 + qb-off-3 (OWN_QB_OFF_M: the 16-head cards' neighbours compute k of their q_b heads in
# checks of 2..6 tokens; qb-off-2 hung in tg97) + dride-1 (OWN_MT_DRIDE=1: the split finishes ride output-b and shared
# down at 4-6 tokens) [+ wa-1 (OWN_ATT_WA=1: WindowAppendM inside the check attention launch) when WAIN=1], all opt-in.
# 1. prompt-1 traces: defaults at 1 / 5 / 64; DR at 4 / 5 / 6 / 64 + DR with DSPLIT_FIN at 5; WA at 2 / 3 / 5 / 6 / 64;
#    QB3 at 2 / 3 / 4 / 5 / 6, QB2 at 2 / 3; all three at 5 (QB arms last: a qb hang must not hide the others)
# 2. 3K traces at 64: default, WA   3. plain: tp97 / tp98 x 2   4. 3K reads at blocks 64 / 256 (whole times)
# 5. guessing: tp98, DR, WA, QB3, all (code, analysis x 2); QB2 once; prose; 3K   6. check timelines with all
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg98
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp98 build exit" $W/build-tp98.log 2>/dev/null; do sleep 10; done
grep -q "tp98 build exit 0" $W/build-tp98.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp98.log >> $sum
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
WAIN=0; grep -q "OWN_ATT_WA" $W/src98/planning/dsv41-fixtures/own_run_v41.cpp && WAIN=1
QB3="OWN_QB_OFF_M=3"; QB2="OWN_QB_OFF_M=2"; DR="OWN_MT_DRIDE=1"; WA="OWN_ATT_WA=1"
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" \
    "h4dr|$TM OWN_PROMPT_BLOCK=4 $DR" "h5dr|$TM OWN_PROMPT_BLOCK=5 $DR" "h6dr|$TM OWN_PROMPT_BLOCK=6 $DR" \
    "h5drf|$TM OWN_PROMPT_BLOCK=5 $DR OWN_MT_DSPLIT_FIN=1" "h64dr|$TB OWN_PROMPT_BLOCK=64 $DR")
[ $WAIN = 1 ] && L1+=("h2wa|$TM OWN_PROMPT_BLOCK=2 $WA" "h3wa|$TM OWN_PROMPT_BLOCK=3 $WA" "h5wa|$T5 $WA" \
    "h6wa|$TM OWN_PROMPT_BLOCK=6 $WA" "h64wa|$TB OWN_PROMPT_BLOCK=64 $WA")
L1+=("h2qb3|$TM OWN_PROMPT_BLOCK=2 $QB3" "h3qb3|$TM OWN_PROMPT_BLOCK=3 $QB3" "h4qb3|$TM OWN_PROMPT_BLOCK=4 $QB3" \
     "h5qb3|$T5 $QB3" "h6qb3|$TM OWN_PROMPT_BLOCK=6 $QB3" "h2qb2|$TM OWN_PROMPT_BLOCK=2 $QB2" "h3qb2|$TM OWN_PROMPT_BLOCK=3 $QB2")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg98 tp98 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
  case $name in h2qb3) okq() { grep -q "^h2qb3 TRACE_IDENTICAL" $sum; }; okq || { echo "gate 1: h2qb3 failed, the other qb arms skipped" >> $sum; break; };; esac
done
if [ $WAIN = 1 ]; then ALLE="$QB3 $DR $WA"; else ALLE="$QB3 $DR"; fi
grep -q "^h2qb3 TRACE_IDENTICAL" $sum && { $W/run_exp.sh tg98 tp98 "h5all|$T5 $ALLE|trace"; sed -i '/^DONE$/d' $sum; fcheck "$tg"; }
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
okn h1 h5 h64 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
DROK=0; okn h4dr h5dr h6dr h5drf h64dr && DROK=1
WAOK=0; [ $WAIN = 1 ] && okn h2wa h3wa h5wa h6wa h64wa && WAOK=1
QBOK=0; okn h2qb3 h3qb3 h4qb3 h5qb3 h6qb3 h2qb2 h3qb2 && QBOK=1
ALLOK=0; [ $DROK = 1 ] && [ $QBOK = 1 ] && { [ $WAIN = 0 ] || [ $WAOK = 1 ]; } && okn h5all && ALLOK=1
echo "gate 1: DROK=$DROK WAOK=$WAOK QBOK=$QBOK ALLOK=$ALLOK (WAIN=$WAIN)" >> $sum
want() { case $1 in *all*) [ $ALLOK = 1 ];; *qb*) [ $QBOK = 1 ];; *dr*) [ $DROK = 1 ];; *wa*) [ $WAOK = 1 ];; *) true;; esac; }
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
p=$W/prompts/p3k-ids.txt; p10=$W/prompts/p10k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference
for k in "b64|OWN_PROMPT_BLOCK=64" "b64wa|OWN_PROMPT_BLOCK=64 $WA"; do
  IFS='|' read -r nm envs <<< "$k"; want $nm || continue
  r t3k_$nm tp98 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc
done
t3ok() { for n in "$@"; do grep -q "^t3k_$n TRACE_IDENTICAL" $sum && grep -q "^t3k_$n IDS40_SAME" $sum || return 1; done; }
t3ok b64 || { echo STOP_GATE2_DEFAULT >> $sum; exit 1; }
[ $WAOK = 1 ] && { t3ok b64wa || { WAOK=0; ALLOK=0; }; }
echo "gate 2: DROK=$DROK WAOK=$WAOK QBOK=$QBOK ALLOK=$ALLOK" >> $sum
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first
$W/run_exp.sh tg98 tp98 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "d98_$rd|98|" "a97_$rd|97|"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg98 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. prompt reads (whole times): 3K at 64 / 256 (256 answers), 10K at 64 / 256 (8 answers, the first token)
for rd in 1 2; do
  for bs in 64 256; do
    r p3k_b${bs}_$rd tp98 $p 256 4096 -1 $D/p3k_b${bs}_$rd-ids.txt $PL OWN_PROMPT_BLOCK=$bs
    same $D/p3k_b${bs}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_b${bs}_$rd
  done
done
# (10K reads dropped after the 15:17 host reset: keep six-card traffic short)
# ---- 5. guessing (prompt blocks of 64)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 n=$2; shift 2
  r $name tp98 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d98_$rd $n $BEST; glog $D/${n}_d98_$rd-spec.txt $W/runs/tg97b/${n}_d97_1-spec.txt ${n}_d98_${rd}_vs_tg97b
    for v in dr wa qb3 all; do
      want $v || continue
      case $v in dr) e="$DR";; wa) e="$WA";; qb3) e="$QB3";; all) e="$ALLE";; esac
      sp ${n}_${v}_$rd $n $BEST $e; glog $D/${n}_${v}_$rd-spec.txt $D/${n}_d98_$rd-spec.txt ${n}_${v}_$rd
    done
  done
done
for n in code analysis; do want qb2 && { sp ${n}_qb2 $n $BEST $QB2; glog $D/${n}_qb2-spec.txt $D/${n}_d98_1-spec.txt ${n}_qb2; }; done
B2=""; [ $DROK = 1 ] && B2="$DR"; [ $WAOK = 1 ] && B2="$B2 $WA"; [ $QBOK = 1 ] && B2="$B2 $QB3"; [ $ALLOK = 1 ] && B2="$ALLE"
sp prose_d98 prose $BEST
[ -n "$B2" ] && sp prose_b2 prose $BEST $B2
r p3k_spec_d98 tp98 $p 256 4096 -1 $D/p3k_spec_d98-ids.txt $BEST OWN_SPEC_LOG=$D/p3k_spec_d98-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
[ -n "$B2" ] && r p3k_spec_b2 tp98 $p 256 4096 -1 $D/p3k_spec_b2-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/p3k_spec_b2-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. check timelines with the best
r tl_ck tp98 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
r tl_ck3 tp98 $PP/code-ids.txt 256 4096 1 $D/tl_ck3-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/tl_ck3-spec.txt OWN_TIMELINE=$D/tl_ck3.txt OWN_TIMELINE_CHECKS=42-49
echo ALLDONE >> $sum
