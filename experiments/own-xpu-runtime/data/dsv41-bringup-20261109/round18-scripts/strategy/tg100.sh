#!/bin/bash
# tg100: gate for tp100 = tp99 + qb-off compiled out (default) + xperm-1 (OWN_PAIR_G128=1: IQ2_S gate+up at 128
# registers) + wa-2 (OWN_ATT_WA=2: per-shape window-append choice) + pb-1 (prompt blocks of 128 / 256: OWN_PB=1 = mask 0x1e: 16-bit rows in weight-reusing forms, parallel expert grouping, 6-bit forms
# without the private scale array, per-role form + token chunk at 65-256 tokens),
# all opt-in. OWN_XLL banned (host freeze 17:59). Six-card traffic per run stays short.
# 1. prompt-1 traces: defaults 1 / 4 / 5 / 6 / 64; G128 at 1 / 5; WA2 at 2 / 3 / 4 / 5 / 6 / 8 / 16 / 64, F=0 at 2 / 5,
#    HEADS_MIN=3 at 5; PB at 1 / 5 / 64 / 128 / 256 (+ each bit
#    alone at 128 / 256); all at 5 and 128   2. 3K traces: default 64, WA2 64, PB 64 / 256
# 3. plain d100 / g128 ×2 + one-token timelines   4. 3K reads: d100 and PB back to back at 64 / 128 / 256; 0x8 at 64, 0x16 at 256
# 5. guessing code / analysis ×2: d100, wa1, wa2, vocab; prose; 3K   6. check timelines
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg100
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp100 build exit" $W/build-tp100.log 2>/dev/null; do sleep 10; done
grep -q "tp100 build exit 0" $W/build-tp100.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp100.log >> $sum
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
G1="OWN_PAIR_G128=1"; WA1="OWN_ATT_WA=1"; WA2="OWN_ATT_WA=2"; PB="${PB:-OWN_PB=1}"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"; ALLE="$G1 $WA2 $PB"
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" "h4|$TM OWN_PROMPT_BLOCK=4" "h6|$TM OWN_PROMPT_BLOCK=6" \
    "h1g|$T1 $G1" "h5g|$T5 $G1" \
    "h2w2|$TM OWN_PROMPT_BLOCK=2 $WA2" "h3w2|$TM OWN_PROMPT_BLOCK=3 $WA2" "h4w2|$TM OWN_PROMPT_BLOCK=4 $WA2" "h5w2|$T5 $WA2" \
    "h6w2|$TM OWN_PROMPT_BLOCK=6 $WA2" "h8w2|$TM OWN_PROMPT_BLOCK=8 $WA2" "h2w2f0|$TM OWN_PROMPT_BLOCK=2 $WA2 OWN_ATT_F=0" \
    "h5w2f0|$T5 $WA2 OWN_ATT_F=0" "h5w2hm3|$T5 $WA2 OWN_TP_HEADS_MIN=3" "h16w2|$TB OWN_PROMPT_BLOCK=16 $WA2" \
    "h64w2|$TB OWN_PROMPT_BLOCK=64 $WA2" \
    "h1pb|$T1 $PB" "h5pb|$T5 $PB" "h64pb|$TB OWN_PROMPT_BLOCK=64 $PB" "h128pb|$TB OWN_PROMPT_BLOCK=128 $PB" \
    "h256pb|$TB OWN_PROMPT_BLOCK=256 $PB" "h128|$TB OWN_PROMPT_BLOCK=128" "h256|$TB OWN_PROMPT_BLOCK=256" \
    "h128pb2|$TB OWN_PROMPT_BLOCK=128 OWN_PB=0x2" "h128pb4|$TB OWN_PROMPT_BLOCK=128 OWN_PB=0x4" \
    "h128pb8|$TB OWN_PROMPT_BLOCK=128 OWN_PB=0x8" "h128pb16|$TB OWN_PROMPT_BLOCK=128 OWN_PB=0x10" \
    "h256pb2|$TB OWN_PROMPT_BLOCK=256 OWN_PB=0x2" "h256pb4|$TB OWN_PROMPT_BLOCK=256 OWN_PB=0x4" \
    "h256pb8|$TB OWN_PROMPT_BLOCK=256 OWN_PB=0x8" "h256pb16|$TB OWN_PROMPT_BLOCK=256 OWN_PB=0x10")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg100 tp100 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
okn h1 h5 h64 h4 h6 h128 h256 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
GOK=0; okn h1g h5g && GOK=1
WAOK=0; okn h2w2 h3w2 h4w2 h5w2 h6w2 h8w2 h2w2f0 h5w2f0 h5w2hm3 h16w2 h64w2 && WAOK=1
PBOK=0; okn h1pb h5pb h64pb h128pb h256pb h128pb2 h128pb4 h128pb8 h128pb16 h256pb2 h256pb4 h256pb8 h256pb16 && PBOK=1
ALLOK=0
if [ $GOK = 1 ] && [ $WAOK = 1 ] && [ $PBOK = 1 ]; then
  for k in "h5all|$T5 $ALLE" "h128all|$TB OWN_PROMPT_BLOCK=128 $ALLE"; do
    IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg100 tp100 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum; fcheck "$tg"
  done
  okn h5all h128all && ALLOK=1
fi
echo "gate 1: GOK=$GOK WAOK=$WAOK PBOK=$PBOK ALLOK=$ALLOK" >> $sum
want() { case $1 in *all*) [ $ALLOK = 1 ];; *pb*) [ $PBOK = 1 ];; *w2*|*wa*) [ $WAOK = 1 ];; *g128*) [ $GOK = 1 ];; *) true;; esac; }
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
for k in "b64|OWN_PROMPT_BLOCK=64" "b256|OWN_PROMPT_BLOCK=256" "b64w2|OWN_PROMPT_BLOCK=64 $WA2" "b64pb|OWN_PROMPT_BLOCK=64 $PB" \
         "b128pb|OWN_PROMPT_BLOCK=128 $PB" "b256pb|OWN_PROMPT_BLOCK=256 $PB"; do
  IFS='|' read -r nm envs <<< "$k"; want $nm || continue
  r t3k_$nm tp100 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc
done
t3ok() { for n in "$@"; do grep -q "^t3k_$n TRACE_IDENTICAL" $sum && grep -q "^t3k_$n IDS40_SAME" $sum || return 1; done; }
t3ok b64 b256 || { echo STOP_GATE2_DEFAULT >> $sum; exit 1; }
[ $WAOK = 1 ] && { t3ok b64w2 || { WAOK=0; ALLOK=0; }; }
[ $PBOK = 1 ] && { t3ok b64pb b128pb b256pb || { PBOK=0; ALLOK=0; }; }
echo "gate 2: GOK=$GOK WAOK=$WAOK PBOK=$PBOK ALLOK=$ALLOK" >> $sum
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first; one-token timelines
$W/run_exp.sh tg100 tp100 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "d100_$rd|" "g128_$rd|$G1"; do
    IFS='|' read -r name envs <<< "$k"; want $name || continue
    $W/run_exp.sh tg100 tp100 "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
r tl_one tp100 $P1 64 4096 -1 $D/tl_one-ids.txt $PL OWN_TIMELINE=$D/tl_one.txt
want g128 && r tl_one_g tp100 $P1 64 4096 -1 $D/tl_one_g-ids.txt $PL $G1 OWN_TIMELINE=$D/tl_one_g.txt
# ---- 4. 3K prompt reads (whole times, 256 answers)
for rd in 1 2; do
  for k in "p3k_d100_64_$rd|64|" "p3k_pb_64_$rd|64|$PB" "p3k_pb8_64_$rd|64|OWN_PB=0x8" "p3k_d100_128_$rd|128|" \
           "p3k_pb_128_$rd|128|$PB" "p3k_d100_256_$rd|256|" "p3k_pb_256_$rd|256|$PB" "p3k_pb16_256_$rd|256|OWN_PB=0x16"; do
    IFS='|' read -r name bs envs <<< "$k"; want $name || continue
    r $name tp100 $p 256 4096 -1 $D/$name-ids.txt $PL OWN_PROMPT_BLOCK=$bs $envs
    same $D/$name-ids.txt $W/runs/e52/p3kplain-ids.txt 256 $name
  done
done
# ---- 5. guessing (prompt blocks of 64)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 n=$2; shift 2
  r $name tp100 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d100_$rd $n $BEST; glog $D/${n}_d100_$rd-spec.txt $W/runs/tg99c/${n}_d99_1-spec.txt ${n}_d100_${rd}_vs_tg99c
    for v in wa1 w2 voc all; do
      want $v || continue
      case $v in wa1) e="$WA1";; w2) e="$WA2";; voc) e="$VOC";; all) e="$ALLE";; esac
      sp ${n}_${v}_$rd $n $BEST $e
      [ $v != voc ] && glog $D/${n}_${v}_$rd-spec.txt $D/${n}_d100_$rd-spec.txt ${n}_${v}_$rd
    done
  done
done
B2=""; [ $GOK = 1 ] && B2="$G1"; [ $WAOK = 1 ] && B2="$B2 $WA2"
sp prose_d100 prose $BEST
[ -n "$B2" ] && sp prose_b2 prose $BEST $B2
sp prose_voc prose $BEST $VOC
r p3k_spec_d100 tp100 $p 256 4096 -1 $D/p3k_spec_d100-ids.txt $BEST OWN_SPEC_LOG=$D/p3k_spec_d100-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
[ -n "$B2" ] && r p3k_spec_b2 tp100 $p 256 4096 -1 $D/p3k_spec_b2-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/p3k_spec_b2-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. check timelines with the best
r tl_ck tp100 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $B2 OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
