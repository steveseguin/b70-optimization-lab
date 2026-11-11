#!/bin/bash
# tg97b: tg97 continued without qb-off-2 (h2qbm hung both heavy cards at 14:02; defaults passed). tg97: gate for tp97 = tp96 with the tg96b winners as defaults (OWN_ATT_T=1, OWN_MT_CK=1, OWN_MT_RUX=1 CAP=6)
# + qb-off-2 (opt-in OWN_QB_OFF_M: the 16-head cards' neighbours compute k of their q_b heads in checks of 2..6 tokens)
# + k7-2 (opt-in OWN_K7=3: the stream mix's dot sums ride the exchanges; k7-1 timed out in tg96).
# 1. prompt-1 traces: defaults at 1 / 2 / 3 / 4 / 5 / 6 / 16 / 64 / 256, old defaults at 5 / 64; QBM at 2-6, QB=3 / 2
#    at 2 / 3; K7 = 3 / 1 / 2 at 1, K7 at 5 / 16 / 64 / 256; K7 + QBM at 5
# 2. 3K traces: defaults at 64 / 256, K7 at 64
# 3. plain: tp96 + ATT / tp97 / K7, alternated twice   4. 3K read: tp96 + ATT + RUX / tp97 (x 2)
# 5. guessing: tp97, QBM, K7, QBM + K7 (code, analysis x 2); QB=3, QB=2, TAU 0.45 / 0.40 once; prose; 3K
# 6. one-token timeline; check timelines at checks 20-27 and 42-49 with the best
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg97b
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
grep -E "^(h1|h2|h3|h4|h5|h6|h16|h64|h256|h5old|h64old) (TRACE_IDENTICAL|IDS40_SAME)$" $W/runs/tg97/summary.txt > $sum # tg97 (qb-off-2 hung at h2qbm)
grep -q "tp97 build exit 0" $W/build-tp97.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp97.log >> $sum
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
OLD="OWN_ATT_T=0 OWN_MT_CK=0 OWN_MT_RUX=0"
QBM="OWN_QB_OFF_M=4,3,3,4,3"
K7="OWN_K7=3"
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h1k7|$T1 $K7" "h1k71|$T1 OWN_K7=1" "h1k72|$T1 OWN_K7=2" "h5k7|$T5 $K7" "h16k7|$TB OWN_PROMPT_BLOCK=16 $K7" \
         "h64k7|$TB OWN_PROMPT_BLOCK=64 $K7" "h256k7|$TB OWN_PROMPT_BLOCK=256 $K7" "h1k7b|$T1 $K7"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg97b tp97 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
okn h1 h2 h3 h4 h5 h6 h16 h64 h256 h5old h64old || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
QBOK=0 # qb-off-2 hung in tg97 (h2qbm, 14:02)
K7OK=0; okn h1k7 h1k71 h1k72 h5k7 h16k7 h64k7 h256k7 h1k7b && K7OK=1
[ $K7OK = 1 ] && [ $QBOK = 1 ] && { okn h5k7qbm || { echo "gate 1: K7 + QBM differ" >> $sum; K7OK=0; }; }
echo "gate 1: QBOK=$QBOK K7OK=$K7OK" >> $sum
# want NAME: skip the arms of a failed patch
want() { case $1 in *all*) [ $K7OK = 1 ] && [ $QBOK = 1 ];; *qb*) [ $QBOK = 1 ];; *k7*) [ $K7OK = 1 ];; *) true;; esac; }
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
# ---- 2. 3K traces against the tp84 reference
for k in "b64|OWN_PROMPT_BLOCK=64" "b256|OWN_PROMPT_BLOCK=256" "b64k7|OWN_PROMPT_BLOCK=64 $K7"; do
  IFS='|' read -r nm envs <<< "$k"; want $nm || continue
  r t3k_$nm tp97 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
t3ok() { for n in "$@"; do grep -q "^t3k_$n TRACE_IDENTICAL" $sum && grep -q "^t3k_$n IDS40_SAME" $sum || return 1; done; }
t3ok b64 b256 || { echo STOP_GATE2_DEFAULT >> $sum; exit 1; }
[ $K7OK = 1 ] && { t3ok b64k7 || K7OK=0; }
echo "gate 2: QBOK=$QBOK K7OK=$K7OK" >> $sum
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg97b tp97 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a96_$rd|96|OWN_ATT_T=1" "d97_$rd|97|" "k7_$rd|97|$K7"; do
    IFS='|' read -r name b envs <<< "$k"; want $name || continue; $W/run_exp.sh tg97b tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "a96|96|OWN_ATT_T=1 OWN_MT_RUX=1 OWN_MT_RUX_CAP=6" "d97|97|"; do
    IFS='|' read -r nm b extra <<< "$k"
    r p3k_${nm}_$rd tp$b $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $extra
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 5. guessing (prompt blocks of 64)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 n=$2; shift 2
  r $name tp97 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
ALL="$QBM $K7"
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d97_$rd $n $BEST;        glog $D/${n}_d97_$rd-spec.txt $W/runs/tg96b/${n}_all_1-spec.txt ${n}_d97_${rd}_vs_tg96b_all
    want qbm && { sp ${n}_qbm_$rd $n $BEST $QBM; } && glog $D/${n}_qbm_$rd-spec.txt $D/${n}_d97_$rd-spec.txt ${n}_qbm_$rd
    want k7 && { sp ${n}_k7_$rd $n $BEST $K7; } && glog $D/${n}_k7_$rd-spec.txt $D/${n}_d97_$rd-spec.txt ${n}_k7_$rd
    want all && { sp ${n}_all_$rd $n $BEST $ALL; } && glog $D/${n}_all_$rd-spec.txt $D/${n}_d97_$rd-spec.txt ${n}_all_$rd
  done
done
B2=""; [ $QBOK = 1 ] && B2="$QBM"; [ $K7OK = 1 ] && B2="$B2 $K7"
for n in code analysis; do
  want qb3 && { sp ${n}_qb3 $n $BEST OWN_QB_OFF_M=3; glog $D/${n}_qb3-spec.txt $D/${n}_d97_1-spec.txt ${n}_qb3; }
  want qb2 && { sp ${n}_qb2 $n $BEST OWN_QB_OFF_M=2; glog $D/${n}_qb2-spec.txt $D/${n}_d97_1-spec.txt ${n}_qb2; }
  sp ${n}_tau45 $n $BEST $B2 OWN_SPEC_TAU=0.45
  sp ${n}_tau40 $n $BEST $B2 OWN_SPEC_TAU=0.40
done
sp prose_d97 prose $BEST
[ -n "$B2" ] && sp prose_b2 prose $BEST $B2
r p3k_spec_d97 tp97 $p 256 4096 -1 $D/p3k_spec_d97-ids.txt $BEST OWN_SPEC_LOG=$D/p3k_spec_d97-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
[ -n "$B2" ] && r p3k_spec_b2 tp97 $p 256 4096 -1 $D/p3k_spec_b2-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/p3k_spec_b2-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. timelines
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
ON=""; [ $K7OK = 1 ] && ON="$K7"
r tl_one tp97 $P1 64 4096 -1 $D/tl_one-ids.txt $PL $ON OWN_TIMELINE=$D/tl_one.txt
r tl_ck tp97 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
r tl_ck3 tp97 $PP/code-ids.txt 256 4096 1 $D/tl_ck3-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/tl_ck3-spec.txt OWN_TIMELINE=$D/tl_ck3.txt OWN_TIMELINE_CHECKS=42-49
echo ALLDONE >> $sum
