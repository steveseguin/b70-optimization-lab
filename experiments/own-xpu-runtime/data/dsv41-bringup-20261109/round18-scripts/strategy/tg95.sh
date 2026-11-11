#!/bin/bash
# tg95: gate for tp95 = tp93 + the default flips (OWN_MT_SKNORM=15, OWN_MT_HCPP=1, OWN_MT_DSPLIT_MIN=4,
# OWN_MT_SKDOTS_MIN=4; tg93 / tune92) + attn-a1 (opt-in: OWN_ATT_T=1 = sparse attention in one launch per layer,
# SparseOutF; OWN_ATT_F=0 the two-launch fallback; blocks > 8 tokens unchanged). Coverage from attn/README "Gate".
# 1. prompt-1 traces: the new defaults at blocks 1 / 5 / 16 / 64 / 256, the old forms (tp93 defaults) at 5 / 64,
#    OWN_ATT_T=1 at 1 / 2 / 4 / 5 / 6 / 8 / 16 / 64 / 256, ATT_F=0 at 1 / 5, ATT + 12 heads (TP_HEADS_MIN=3) at 5
# 2. 3K traces at 64 (default, ATT; the decode steps run the one-token attention at 3K slots)
# 3. plain speed: tp93 / tp95 / tp95 + ATT / + ATT_F=0, alternated twice
# 4. 3K read: tp95 / + ATT at 64, ATT at 256, alternated twice
# 5. guessing: default, ATT (code, analysis x 2), ATT_F=0 (x 1); prose; 3K
# 6. card 2 kernel profile and a check timeline with ATT + CK (+ QB4)
# + qb-off-1 (qboff/README.md, opt-in OWN_QB_OFF=k: each 16-head card's two neighbours compute k of its q_b heads
#   first and push them; one-token steps only): traces k = 2 / 3 / 4, 4 with OWN_QB_OFF_WG=1, 4 + ATT, at block 1 and 5;
#   3K traces 4 / 4 + ATT; plain 2 / 3 / 4 / 4 + ATT; 3K read ATT + QB4; guessing ATT + CK + QB4
# + ck (pa/ck.patch, opt-in OWN_MT_CK=1: the checks' dense rows in their own weight-stationary forms per block size
#   2-6, q_a + kv pair forms; off = tp94 forms exactly): traces at blocks 2-6 (+ RIDE=0 at 2 / 3, + ATT at 2 / 5),
#   16; guessing CK and ATT + CK
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg95
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp95 build exit" $W/build-tp95.log 2>/dev/null; do sleep 10; done
grep -q "tp95 build exit 0" $W/build-tp95.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp95.log >> $sum
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
QB4="OWN_QB_OFF=4"
TM="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 $G"
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h1|$T1" "h5|$T5" "h16|$TB OWN_PROMPT_BLOCK=16" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" \
         "h5old|$T5 $OLD" "h64old|$TB OWN_PROMPT_BLOCK=64 $OLD" \
         "h1att|$T1 $ATT" "h2att|$TM OWN_PROMPT_BLOCK=2 $ATT" "h4att|$TM OWN_PROMPT_BLOCK=4 $ATT" "h5att|$T5 $ATT" \
         "h6att|$TM OWN_PROMPT_BLOCK=6 $ATT" "h8att|$TM OWN_PROMPT_BLOCK=8 $ATT" "h16att|$TB OWN_PROMPT_BLOCK=16 $ATT" \
         "h64att|$TB OWN_PROMPT_BLOCK=64 $ATT" "h256att|$TB OWN_PROMPT_BLOCK=256 $ATT" \
         "h1attf0|$T1 $ATT OWN_ATT_F=0" "h5attf0|$T5 $ATT OWN_ATT_F=0" "h5atthm3|$T5 $ATT OWN_TP_HEADS_MIN=3" \
         "h2ck|$TM OWN_PROMPT_BLOCK=2 $CK" "h3ck|$TM OWN_PROMPT_BLOCK=3 $CK" "h4ck|$TM OWN_PROMPT_BLOCK=4 $CK" \
         "h5ck|$T5 $CK" "h6ck|$TM OWN_PROMPT_BLOCK=6 $CK" "h16ck|$TB OWN_PROMPT_BLOCK=16 $CK" \
         "h2ckr0|$TM OWN_PROMPT_BLOCK=2 $CK OWN_MT_RIDE=0" "h3ckr0|$TM OWN_PROMPT_BLOCK=3 $CK OWN_MT_RIDE=0" \
         "h2ckatt|$TM OWN_PROMPT_BLOCK=2 $CK $ATT" "h5ckatt|$T5 $CK $ATT" \
         "h1qb4|$T1 $QB4" "h1qb3|$T1 OWN_QB_OFF=3" "h1qb2|$T1 OWN_QB_OFF=2" "h1qb4wg1|$T1 $QB4 OWN_QB_OFF_WG=1" \
         "h1qb4att|$T1 $QB4 $ATT" "h5qb4|$T5 $QB4" "h5all|$T5 $QB4 $ATT $CK"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg95 tp95 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $sum && { echo STOP_GATE1 >> $sum; exit 1; }
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
for k in "b64|OWN_PROMPT_BLOCK=64" "b64att|OWN_PROMPT_BLOCK=64 $ATT" "b64qb4|OWN_PROMPT_BLOCK=64 $QB4" "b64all|OWN_PROMPT_BLOCK=64 $ATT $QB4 $CK"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp95 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg95 tp95 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a93_$rd|93|" "d95_$rd|95|" "att_$rd|95|$ATT" "attf0_$rd|95|$ATT OWN_ATT_F=0" "qb2_$rd|95|OWN_QB_OFF=2" \
           "qb3_$rd|95|OWN_QB_OFF=3" "qb4_$rd|95|$QB4" "attqb4_$rd|95|$ATT $QB4"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg95 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "d95|95|" "att|95|$ATT" "att256|95|$ATT OWN_PROMPT_BLOCK=256" "attqb4|95|$ATT $QB4"; do
    IFS='|' read -r nm b extra <<< "$k"
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
  r $name tp95 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d95_$rd $n $BEST;        glog $D/${n}_d95_$rd-spec.txt $W/runs/tg93/${n}_sk44_1-spec.txt ${n}_d95_${rd}_vs_tg93sk44
    sp ${n}_att_$rd $n $BEST $ATT;   glog $D/${n}_att_$rd-spec.txt $D/${n}_d95_$rd-spec.txt ${n}_att_$rd
    sp ${n}_ck_$rd $n $BEST $CK;     glog $D/${n}_ck_$rd-spec.txt $D/${n}_d95_$rd-spec.txt ${n}_ck_$rd
    sp ${n}_attck_$rd $n $BEST $ATT $CK; glog $D/${n}_attck_$rd-spec.txt $D/${n}_d95_$rd-spec.txt ${n}_attck_$rd
    sp ${n}_all_$rd $n $BEST $ATT $CK $QB4; glog $D/${n}_all_$rd-spec.txt $D/${n}_d95_$rd-spec.txt ${n}_all_$rd
  done
done
for n in code analysis; do
  sp ${n}_attf0 $n $BEST $ATT OWN_ATT_F=0; glog $D/${n}_attf0-spec.txt $D/${n}_d95_1-spec.txt ${n}_attf0
done
for n in prose; do
  sp ${n}_d95 $n $BEST
  sp ${n}_attck $n $BEST $ATT $CK
  sp ${n}_all $n $BEST $ATT $CK $QB4
done
for v in d95 attck all; do
  case $v in d95) envs="";; attck) envs="$ATT $CK";; all) envs="$ATT $CK $QB4";; esac
  r p3k_spec_$v tp95 $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 28): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. card 2 kernel profile and a check timeline (default)
r gprof_ck tp95 $PP/code-ids.txt 256 4096 1 $D/gprof_ck-ids.txt $BEST $ATT $CK $QB4 OWN_GPROF=2 OWN_GPROF_CARD=2 OWN_GPROF_DECODE=1
r tl_ck tp95 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $ATT $CK $QB4 OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
