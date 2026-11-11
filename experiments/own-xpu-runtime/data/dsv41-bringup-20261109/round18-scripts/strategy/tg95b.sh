#!/bin/bash
# tg95b: the rest of tg95 without the attention arms (attn-a1 traces differed in tg95: STOP_GATE1). Arms: ck
# (OWN_MT_CK=1) and qb-off-1 (OWN_QB_OFF=k), each only if all its tg95 traces were identical.
# 2. 3K traces at 64: QB4, CK + QB4   3. plain: tp93 / tp95 / QB 2 / 3 / 4 (x 2)   4. 3K read: tp95 / QB4 (x 2)
# 5. guessing: default, CK, CK + QB4 (code, analysis x 2); prose; 3K   6. card 2 profile + check timeline (CK + QB4)
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg95b
T95=$W/runs/tg95/summary.txt
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -qE "ALLDONE|STOP" $T95 2>/dev/null; do sleep 20; done
grep -q "STOP_FAULT\|STOP_BUILD" $T95 && { echo "STOP_TG95_FAULT" >> $sum; exit 1; }
ok() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $T95 && grep -q "^$n IDS40_SAME" $T95 || return 1; done; return 0; }
CKOK=0; QBOK=0
ok h2ck h3ck h4ck h5ck h6ck h16ck h2ckr0 h3ckr0 && CKOK=1
ok h1qb4 h1qb3 h1qb2 h1qb4wg1 h5qb4 && QBOK=1
echo "from tg95 traces: CKOK=$CKOK QBOK=$QBOK" >> $sum
[ $CKOK = 1 ] || [ $QBOK = 1 ] || { echo "STOP_NOTHING_TO_TEST" >> $sum; exit 1; }
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
T2=""; [ $QBOK = 1 ] && T2="b64qb4|OWN_PROMPT_BLOCK=64 $QB4"; [ $QBOK = 1 ] && [ $CKOK = 1 ] && T2="$T2;b64ckqb|OWN_PROMPT_BLOCK=64 $QB4 $CK"
IFS=';' read -ra T2A <<< "$T2"
for k in "${T2A[@]}"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp95 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg95b tp95 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  P3=("a93_$rd|93|" "d95_$rd|95|"); [ $QBOK = 1 ] && P3+=("qb2_$rd|95|OWN_QB_OFF=2" "qb3_$rd|95|OWN_QB_OFF=3" "qb4_$rd|95|$QB4")
  for k in "${P3[@]}"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg95b tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  P4=("d95|95|"); [ $QBOK = 1 ] && P4+=("qb4|95|$QB4")
  for k in "${P4[@]}"; do
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
CQ=""; [ $CKOK = 1 ] && CQ="$CK"; [ $QBOK = 1 ] && CQ="$CQ $QB4"
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d95_$rd $n $BEST;        glog $D/${n}_d95_$rd-spec.txt $W/runs/tg93/${n}_sk44_1-spec.txt ${n}_d95_${rd}_vs_tg93sk44
    if [ $CKOK = 1 ]; then sp ${n}_ck_$rd $n $BEST $CK; glog $D/${n}_ck_$rd-spec.txt $D/${n}_d95_$rd-spec.txt ${n}_ck_$rd; fi
    sp ${n}_cq_$rd $n $BEST $CQ;     glog $D/${n}_cq_$rd-spec.txt $D/${n}_d95_$rd-spec.txt ${n}_cq_$rd
  done
done
sp prose_d95 prose $BEST
sp prose_cq prose $BEST $CQ
for v in d95 cq; do
  case $v in d95) envs="";; cq) envs="$CQ";; esac
  r p3k_spec_$v tp95 $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. card 2 kernel profile and a check timeline (default)
r gprof_ck tp95 $PP/code-ids.txt 256 4096 1 $D/gprof_ck-ids.txt $BEST $CQ OWN_GPROF=2 OWN_GPROF_CARD=2 OWN_GPROF_DECODE=1
r tl_ck tp95 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $CQ OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
