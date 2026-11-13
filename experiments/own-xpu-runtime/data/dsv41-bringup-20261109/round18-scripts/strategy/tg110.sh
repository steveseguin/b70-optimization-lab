#!/bin/bash
# tg110 (2026-11-13): tp110 = tp109 + RUX5 default (e004ace38) + qkv-1 (OWN_QKV_SPLIT default on: q_a + kv rows split by
# card, one gather per layer; qsp110: plain +1.8 %). Gate: traces (defaults, QKV off), 3K traces, plain tp109+RUX5 vs
# tp110 alternated, guessing code / analysis, 3K + 10K reads. No sampler. No b300 / PX halves of 150. No OWN_XLL.
# Speed only from unprofiled runs alternated.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg110
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
memwait() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
until grep -q "tp110 build exit [0-8]" $W/build-tp110.log 2>/dev/null; do sleep 10; done
grep -q "tp110 build exit 0" $W/build-tp110.log || { echo STOP_BUILD >> $sum; exit 1; }
grep "tp110 build exit" $W/build-tp110.log | tail -1 >> $sum
SP=
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
SP= # gpu_sampler off since 2026-11-12 19:20: its 120 card-register reads per second are CPU waits on the cards (host-reset victims)
gap() { rm -f $W/six.active; echo "gap $(date +%T)" >> $sum; sleep 200; until [ ! -e $W/six.active ]; do sleep 5; done; touch $W/six.active
  while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done; }
tg=$(date '+%Y-%m-%d %H:%M:%S')
echo "start $tg" >> $sum
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
TM="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 $G"
AX="OWN_PAIR_G128=1 OWN_MT_PACE=1" # A (tp102) = tp104's defaults
OFF="OWN_PAIR_G128=0 OWN_MT_PACE=0 OWN_PB=0 OWN_ATT_WA=0"
R127="OWN_MT_PACE_ROLES=127"
PX="OWN_PX=1 OWN_PX_CHECK=1"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
PB="OWN_PX=1 OWN_PX_BIG=1 OWN_PX_CHECK=1"
W8="OWN_PX_WGS=16,16,16,16,8,8,16,16"; W4="OWN_PX_WGS=16,16,16,16,4,4,16,16"



# ---- 1. prompt-1 traces (tp110 against runs/ab1): defaults (now RUX5 + QKV split), then QKV off at 1 / 4 / 64
Q0="OWN_QKV_SPLIT=0"
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" "h4|$TM OWN_PROMPT_BLOCK=4" \
    "h2|$TM OWN_PROMPT_BLOCK=2" "h3|$TM OWN_PROMPT_BLOCK=3" "h6|$TM OWN_PROMPT_BLOCK=6" "h16|$TB OWN_PROMPT_BLOCK=16" \
    "h1q0|$T1 $Q0" "h4q0|$TM OWN_PROMPT_BLOCK=4 $Q0" "h64q0|$TB OWN_PROMPT_BLOCK=64 $Q0")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh tg110 tp110 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn h1 h5 h64 h256 h4 h2 h3 h6 h16 h1q0 h4q0 h64q0 || { echo STOP_GATE1 >> $sum; exit 1; }
echo "gate 1: defaults + QKV off identical" >> $sum
gap
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  memwait; echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref
t3k() { local nm=$1; shift
  r t3k_$nm tp110 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
t3k b512 OWN_PROMPT_BLOCK=512 $PB
t3k b256 OWN_PROMPT_BLOCK=256
okn t3k_b512 t3k_b256 || { echo STOP_GATE2 >> $sum; exit 1; }
echo "gate 2: 3K traces identical" >> $sum
gap
# ---- 3. plain speed alternated x2: a = tp109 + RUX5 (tp110 without the QKV split), b = tp110 defaults
memwait; $W/run_exp.sh tg110 tp110 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
ARMS=("a|tp109|$PL OWN_RUX5=1" "b|tp110|$PL")
for rd in 1 2; do for k in "${ARMS[@]}"; do IFS='|' read -r name bin envs <<< "$k"; memwait; $W/run_exp.sh tg110 $bin "${name}_$rd|$envs|speed"; sed -i '/^DONE$/d' $sum; done; done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
fcheck "$tg"
gap
# ---- 4. guessing (BEST + vocabulary) on tp110 defaults, code and analysis x2 (tg109 c arms = tp109 + RUX5: code 155.1, analysis 173.5)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5 $VOC"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 b=$2 n=$3; shift 3
  r $name $b $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt
  glog $D/$name-spec.txt $W/runs/tg105v/${n}_v1-spec.txt ${name}_vs_v1; }
for n in code analysis; do sp ${n}_b1 tp110 $n $BEST; sp ${n}_b2 tp110 $n $BEST; done
gap
# ---- 5. 3K reads (256 answers) x2 and 10K once on tp110 defaults (px-512, copy engine, RUX4 by default)
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
for rd in 1 2; do
  r p3k_b_$rd tp110 $p 256 4096 -1 $D/p3k_b_$rd-ids.txt $PL $P5; same $D/p3k_b_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_b_$rd
done
p10=$W/prompts/p10k-ids.txt
r p10k_b tp110 $p10 64 16384 -1 $D/p10k_b-ids.txt $PL $P5; same $D/p10k_b-ids.txt $W/runs/tg107/p10k_bcs-ids.txt 64 p10k_b
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER\|TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo "SOME_DIFFER" >> $sum; echo ALLDONE >> $sum; exit 0; }
echo ALLDONE >> $sum
