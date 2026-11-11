#!/bin/bash
# tg96: gate for tp96 = tp96 + k7-1 (opt-in OWN_K7=3: the stream mix's dot sums ride the output-b / ffn-rows
# exchanges as per-card partials, the norm alone after; one-token steps; bits 1 / 2 = the two sites) + attn-a2
# (OWN_ATT_T=1: the one-launch attention with L1-uncached score hand-over; a1 differed in tg96).
# 1. prompt-1 traces: defaults 1 / 5 / 64; K7 = 3 / 1 / 2 at block 1, K7 at 5 / 16 / 64 / 256; ATT at 1 / 2 / 4 / 5 /
#    6 / 8 / 16 / 64 / 256, ATT_F=0 at 1, ATT + 12 heads at 5, ATT + CK at 2 / 5; ATT + K7 at 1, + CK at 5
# 2. 3K traces at 64: default, K7, ATT, ATT + K7 + CK
# 3. plain: tp96 / tp96 / K7 / ATT / ATT + K7, alternated twice   4. 3K read: tp96 / ATT + K7 (x 2)
# 5. guessing: default, K7, ATT, ATT + K7 + CK (code, analysis x 2); prose; 3K
# 6. one-token profile (card 2) + plain timeline with ATT + K7; check profile + check timeline with all
# + rux-1 (opt-in OWN_MT_RUX=1 OWN_MT_RUX_CAP=6: prompt-block expert kernels, two rows per sub-group; checks untouched
#   below OWN_MT_RUX_MIN=16) and OWN_MT_EU_BIG=0 (cap 6 from 128 tokens, existing switch): traces at 64 / 256, 3K
#   traces at 64 / 128 / 256, 3K read at 64 / 128 / 256 (x 2)
# + runtime arms for the 2-token check path (ck2tok/README.md), on top of CK: OWN_MT_XPUSH=0 / 2, OWN_XPULL_MIN=6912,
#   OWN_MT_SKDOTS_MIN=2 / 3, OWN_MT_FIN_QB=0 (traces at blocks 2 / 3; guessing code + analysis once each)
# + ck-2 (pa/README-ck2.txt: OWN_MT_CK mask over M = 2..6, OWN_MT_CK_MS, OWN_MT_CK_FIN = the q_b + riding finish fix,
#   q_a + kv pair forms with riding dots): traces CK at 2-6, FIN alone at 2 / 3, MS=2,4,5,6 at 3; guessing CK,
#   FIN alone, MS x 2; an M = 3 check timeline (OWN_TIMELINE_CHECKS=42-49)
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg96
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp96 build exit" $W/build-tp96.log 2>/dev/null; do sleep 10; done
grep -q "tp96 build exit 0" $W/build-tp96.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp96.log >> $sum
SP=
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
tg=$(date '+%Y-%m-%d %H:%M:%S')
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
OLD="OWN_MT_SKNORM=0 OWN_MT_HCPP=0 OWN_MT_DSPLIT_MIN=2 OWN_MT_SKDOTS_MIN=2"
ATT="OWN_ATT_T=1"
CK="OWN_MT_CK=1"
CKF="OWN_MT_CK=0 OWN_MT_CK_FIN=1"
CKM="OWN_MT_CK_MS=2,4,5,6"
QB4="OWN_QB_OFF=4"
TM="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 $G"
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
K7="OWN_K7=3"
RUX="OWN_MT_RUX=1 OWN_MT_RUX_CAP=6"
for k in "h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" \
         "h1k7|$T1 $K7" "h1k71|$T1 OWN_K7=1" "h1k72|$T1 OWN_K7=2" "h5k7|$T5 $K7" "h16k7|$TB OWN_PROMPT_BLOCK=16 $K7" \
         "h64k7|$TB OWN_PROMPT_BLOCK=64 $K7" "h256k7|$TB OWN_PROMPT_BLOCK=256 $K7" \
         "h1att|$T1 $ATT" "h2att|$TM OWN_PROMPT_BLOCK=2 $ATT" "h4att|$TM OWN_PROMPT_BLOCK=4 $ATT" "h5att|$T5 $ATT" \
         "h6att|$TM OWN_PROMPT_BLOCK=6 $ATT" "h8att|$TM OWN_PROMPT_BLOCK=8 $ATT" "h16att|$TB OWN_PROMPT_BLOCK=16 $ATT" \
         "h64att|$TB OWN_PROMPT_BLOCK=64 $ATT" "h256att|$TB OWN_PROMPT_BLOCK=256 $ATT" \
         "h1attf0|$T1 $ATT OWN_ATT_F=0" "h5atthm3|$T5 $ATT OWN_TP_HEADS_MIN=3" \
         "h2attck|$TM OWN_PROMPT_BLOCK=2 $ATT $CK" "h5attck|$T5 $ATT $CK" "h1attk7|$T1 $ATT $K7" "h5all|$T5 $ATT $K7 $CK" \
         "h64rux|$TB OWN_PROMPT_BLOCK=64 $RUX" "h256rux|$TB OWN_PROMPT_BLOCK=256 $RUX" "h256eub0|$TB OWN_PROMPT_BLOCK=256 OWN_MT_EU_BIG=0" \
         "h2xp0|$TM OWN_PROMPT_BLOCK=2 $CK OWN_MT_XPUSH=0" "h2xp2|$TM OWN_PROMPT_BLOCK=2 $CK OWN_MT_XPUSH=2" \
         "h2xpl|$TM OWN_PROMPT_BLOCK=2 $CK OWN_XPULL_MIN=6912" "h3xpl|$TM OWN_PROMPT_BLOCK=3 $CK OWN_XPULL_MIN=6912" \
         "h2sd2|$TM OWN_PROMPT_BLOCK=2 $CK OWN_MT_SKDOTS_MIN=2" "h3sd3|$TM OWN_PROMPT_BLOCK=3 $CK OWN_MT_SKDOTS_MIN=3" \
         "h2fq0|$TM OWN_PROMPT_BLOCK=2 $CK OWN_MT_FIN_QB=0" "h3fq0|$TM OWN_PROMPT_BLOCK=3 $CK OWN_MT_FIN_QB=0" \
         "h2ck|$TM OWN_PROMPT_BLOCK=2 $CK" "h3ck|$TM OWN_PROMPT_BLOCK=3 $CK" "h4ck|$TM OWN_PROMPT_BLOCK=4 $CK" "h5ck|$T5 $CK" \
         "h6ck|$TM OWN_PROMPT_BLOCK=6 $CK" "h2fin|$TM OWN_PROMPT_BLOCK=2 $CKF" "h3fin|$TM OWN_PROMPT_BLOCK=3 $CKF" \
         "h3ms|$TM OWN_PROMPT_BLOCK=3 $CKM" "h4ms|$TM OWN_PROMPT_BLOCK=4 $CKM"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg96 tp96 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
grep -q "exit [^0]" $sum && { echo STOP_EXIT1 >> $sum; exit 1; }
okn h1 h5 h64 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
K7OK=0; okn h1k7 h1k71 h1k72 h5k7 h16k7 h64k7 h256k7 && K7OK=1
ATTOK=0; okn h1att h2att h4att h5att h6att h8att h16att h64att h256att h1attf0 h5atthm3 h2attck h5attck && ATTOK=1
[ $K7OK = 1 ] && [ $ATTOK = 1 ] && { okn h1attk7 h5all || { ATTOK=0; K7OK=0; }; }
echo "gate 1: K7OK=$K7OK ATTOK=$ATTOK" >> $sum
RUXOK=0; okn h64rux h256rux h256eub0 && RUXOK=1
echo "gate 1: RUXOK=$RUXOK" >> $sum
okn h2ck h3ck h4ck h5ck h6ck h2fin h3fin h3ms h4ms || { echo STOP_GATE1_CK2 >> $sum; exit 1; }
XA=""
for a in xp0 xp2 xpl sd2 fq0; do case $a in xpl) t="h2xpl h3xpl";; sd2) t="h2sd2 h3sd3";; fq0) t="h2fq0 h3fq0";; *) t="h2$a";; esac
  okn $t && XA="$XA $a"; done
okn h3sd3 && XA="$XA sd3"
echo "gate 1: runtime arms that passed:$XA" >> $sum
[ $K7OK = 1 ] || [ $ATTOK = 1 ] || [ $RUXOK = 1 ] || { echo STOP_GATE1 >> $sum; exit 1; }
# want NAME: skip the arms of a failed patch (names with att / k7 / all)
want() { case $1 in *rux*|*eub0*) [ $RUXOK = 1 ];; *all*|*attk7*) [ $K7OK = 1 ] && [ $ATTOK = 1 ];; *att*) [ $ATTOK = 1 ];; *k7*) [ $K7OK = 1 ];; *) true;; esac; }
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
for k in "b64|OWN_PROMPT_BLOCK=64" "b64k7|OWN_PROMPT_BLOCK=64 $K7" "b64att|OWN_PROMPT_BLOCK=64 $ATT" "b64all|OWN_PROMPT_BLOCK=64 $ATT $K7 $CK" \
         "b64rux|OWN_PROMPT_BLOCK=64 $RUX" "b128rux|OWN_PROMPT_BLOCK=128 $RUX" "b256rux|OWN_PROMPT_BLOCK=256 $RUX" "b256eub0|OWN_PROMPT_BLOCK=256 OWN_MT_EU_BIG=0"; do
  IFS='|' read -r nm envs <<< "$k"; want $nm || continue
  r t3k_$nm tp96 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
t3ok() { for n in "$@"; do grep -q "^t3k_$n TRACE_IDENTICAL" $sum && grep -q "^t3k_$n IDS40_SAME" $sum || return 1; done; }
t3ok b64 || { echo STOP_GATE2_DEFAULT >> $sum; exit 1; }
[ $K7OK = 1 ] && { t3ok b64k7 || K7OK=0; }
[ $ATTOK = 1 ] && { t3ok b64att || ATTOK=0; }
[ $K7OK = 1 ] && [ $ATTOK = 1 ] && { t3ok b64all || { K7OK=0; ATTOK=0; }; }
[ $RUXOK = 1 ] && { t3ok b64rux b128rux b256rux b256eub0 || RUXOK=0; }
echo "gate 2: K7OK=$K7OK ATTOK=$ATTOK RUXOK=$RUXOK" >> $sum
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg96 tp96 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a95_$rd|95|" "d96_$rd|96|" "k7_$rd|96|$K7" "att_$rd|96|$ATT" "attk7_$rd|96|$ATT $K7"; do
    IFS='|' read -r name b envs <<< "$k"; want $name || continue; $W/run_exp.sh tg96 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "d96|96|" "attk7|96|$ATT $K7" "rux|96|$RUX" "rux128|96|$RUX OWN_PROMPT_BLOCK=128" "rux256|96|$RUX OWN_PROMPT_BLOCK=256" \
           "eub0_256|96|OWN_MT_EU_BIG=0 OWN_PROMPT_BLOCK=256"; do
    IFS='|' read -r nm b extra <<< "$k"; want $nm || continue
    r p3k_${nm}_$rd tp$b $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $extra
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 5. guessing (prompt blocks of 64)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 n=$2; shift 2
  r $name tp96 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
ALL="$ATT $K7 $CK"
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d96_$rd $n $BEST;        glog $D/${n}_d96_$rd-spec.txt $W/runs/tg95b/${n}_d95_1-spec.txt ${n}_d96_${rd}_vs_tg95b
    want k7 && { sp ${n}_k7_$rd $n $BEST $K7; } && glog $D/${n}_k7_$rd-spec.txt $D/${n}_d96_$rd-spec.txt ${n}_k7_$rd
    want att && { sp ${n}_att_$rd $n $BEST $ATT; } && glog $D/${n}_att_$rd-spec.txt $D/${n}_d96_$rd-spec.txt ${n}_att_$rd
    want all && { sp ${n}_all_$rd $n $BEST $ALL; } && glog $D/${n}_all_$rd-spec.txt $D/${n}_d96_$rd-spec.txt ${n}_all_$rd
  done
done
for n in code analysis; do
  for rd in 1 2; do
    sp ${n}_ck_$rd $n $BEST $CK;  glog $D/${n}_ck_$rd-spec.txt $D/${n}_d96_1-spec.txt ${n}_ck_$rd
    sp ${n}_ms_$rd $n $BEST $CKM; glog $D/${n}_ms_$rd-spec.txt $D/${n}_d96_1-spec.txt ${n}_ms_$rd
  done
  sp ${n}_fin $n $BEST $CKF; glog $D/${n}_fin-spec.txt $D/${n}_d96_1-spec.txt ${n}_fin
  for a in $XA; do
    case $a in xp0) e="OWN_MT_XPUSH=0";; xp2) e="OWN_MT_XPUSH=2";; xpl) e="OWN_XPULL_MIN=6912";; sd2) e="OWN_MT_SKDOTS_MIN=2";;
               sd3) e="OWN_MT_SKDOTS_MIN=3";; fq0) e="OWN_MT_FIN_QB=0";; esac
    sp ${n}_ck$a $n $BEST $CK $e; glog $D/${n}_ck$a-spec.txt $D/${n}_d96_1-spec.txt ${n}_ck$a
  done
done
sp prose_d96 prose $BEST
want all && sp prose_all prose $BEST $ALL
for v in d96 all; do
  want $v || continue
  case $v in d96) envs="";; all) envs="$ALL";; esac
  r p3k_spec_$v tp96 $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. profiles and timelines
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
ON=""; [ $ATTOK = 1 ] && ON="$ATT"; [ $K7OK = 1 ] && ON="$ON $K7"
r gprof_one tp96 $P1 48 4096 -1 $D/gprof_one-ids.txt $PL $ON OWN_GPROF=2 OWN_GPROF_CARD=2 OWN_GPROF_DECODE=1
r tl_one tp96 $P1 64 4096 -1 $D/tl_one-ids.txt $PL $ON OWN_TIMELINE=$D/tl_one.txt
r tl_one_d tp96 $P1 64 4096 -1 $D/tl_one_d-ids.txt $PL OWN_TIMELINE=$D/tl_one_d.txt
r gprof_ck tp96 $PP/code-ids.txt 256 4096 1 $D/gprof_ck-ids.txt $BEST $ON $CK OWN_GPROF=2 OWN_GPROF_CARD=2 OWN_GPROF_DECODE=1
r tl_ck tp96 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $ON $CK OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
r tl_ck3 tp96 $PP/code-ids.txt 256 4096 1 $D/tl_ck3-ids.txt $BEST $ON $CK OWN_SPEC_LOG=$D/tl_ck3-spec.txt OWN_TIMELINE=$D/tl_ck3.txt OWN_TIMELINE_CHECKS=42-49
r tl_ck3_d tp96 $PP/code-ids.txt 256 4096 1 $D/tl_ck3_d-ids.txt $BEST OWN_SPEC_LOG=$D/tl_ck3_d-spec.txt OWN_TIMELINE=$D/tl_ck3_d.txt OWN_TIMELINE_CHECKS=42-49
echo ALLDONE >> $sum
