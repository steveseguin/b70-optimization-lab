#!/bin/bash
# tg97c: the free runtime tests DSPLIT_FIN=1 / HEADS_MIN=4 at checks + the 3K read order swap, on tp97. tg97b: tg97 continued without qb-off-2 (h2qbm hung both heavy cards at 14:02; defaults passed). tg97: gate for tp97 = tp96 with the tg96b winners as defaults (OWN_ATT_T=1, OWN_MT_CK=1, OWN_MT_RUX=1 CAP=6)
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
D=$W/runs/tg97c
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
: > $sum
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
# ---- 1. prompt-1 traces: the two free runtime tests at checks (ck2tok96 section 4)
DSF="OWN_MT_DSPLIT_FIN=1"; HM4="OWN_TP_HEADS_MIN=4"
for k in "h4dsf|$TM OWN_PROMPT_BLOCK=4 $DSF" "h5dsf|$T5 $DSF" "h6dsf|$TM OWN_PROMPT_BLOCK=6 $DSF" \
         "h4hm4|$TM OWN_PROMPT_BLOCK=4 $HM4" "h5hm4|$T5 $HM4" "h6hm4|$TM OWN_PROMPT_BLOCK=6 $HM4"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg97c tp97 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
DOK=0; okn h4dsf h5dsf h6dsf && DOK=1
HOK=0; okn h4hm4 h5hm4 h6hm4 && HOK=1
echo "gate 1: DOK=$DOK HOK=$HOK" >> $sum
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
# ---- 2. the 3K read, tp97 first this time (tg97b: tp96 + ATT + RUX 497.7 / 497.3 ran first, tp97 493.2 / 492.7)
for rd in 1 2; do
  for k in "d97|97|" "a96|96|OWN_ATT_T=1 OWN_MT_RUX=1 OWN_MT_RUX_CAP=6"; do
    IFS='|' read -r nm b extra <<< "$k"
    r p3k_${nm}_$rd tp$b $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $extra
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 3. guessing
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 n=$2; shift 2
  r $name tp97 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d97_$rd $n $BEST
    [ $DOK = 1 ] && { sp ${n}_dsf_$rd $n $BEST $DSF; glog $D/${n}_dsf_$rd-spec.txt $D/${n}_d97_$rd-spec.txt ${n}_dsf_$rd; }
    [ $HOK = 1 ] && { sp ${n}_hm4_$rd $n $BEST $HM4; glog $D/${n}_hm4_$rd-spec.txt $D/${n}_d97_$rd-spec.txt ${n}_hm4_$rd; }
  done
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
