#!/bin/bash
# tg106 (2026-11-12): tp106 = tp105 + ck2-1 (OWN_CK2: 2-3-token check forms, opt-in) + defaults OWN_FL=3, OWN_U3_NOPAIR=1,
# OWN_MT_EU_HEAVY=0. Gate: traces (defaults + CK2 arms), 3K traces, plain speed tp105 vs tp106, guessing (BEST + vocabulary)
# with and without CK2 alternated, 3K reads. No sampler. No b300.
# No b300 / PX halves of 150 (banned: host resets). Speed only from unprofiled runs alternated.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg106
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
until grep -q "tp106 build exit" $W/build-tp106.log 2>/dev/null; do sleep 10; done
grep -q "tp106 build exit 0" $W/build-tp106.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp106.log >> $sum
SP=
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
SP= # gpu_sampler off since 2026-11-12 19:20: its 120 card-register reads per second are CPU waits on the cards (host-reset victims)
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

# ---- 1. prompt-1 traces (tp106 against runs/ab1)
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" "h4|$TM OWN_PROMPT_BLOCK=4" \
    "h2|$TM OWN_PROMPT_BLOCK=2" "h3|$TM OWN_PROMPT_BLOCK=3" "h6|$TM OWN_PROMPT_BLOCK=6" \
    "h2c|$TM OWN_PROMPT_BLOCK=2 OWN_CK2=1" "h3c|$TM OWN_PROMPT_BLOCK=3 OWN_CK2=1" "h4c|$TM OWN_PROMPT_BLOCK=4 OWN_CK2=1" \
    "h5c|$T5 OWN_CK2=1" "h6c|$TM OWN_PROMPT_BLOCK=6 OWN_CK2=1" "h1c|$T1 OWN_CK2=1" \
    "h2c1|$TM OWN_PROMPT_BLOCK=2 OWN_CK2=1 OWN_CK2_FORMS=1" "h3c2|$TM OWN_PROMPT_BLOCK=3 OWN_CK2=1 OWN_CK2_FORMS=2" \
    "h1old|$T1 OWN_FL=0 OWN_U3_NOPAIR=0 OWN_MT_EU_HEAVY=1")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh tg106 tp106 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn h1 h5 h64 h256 h4 h2 h3 h6 h1old || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
CK=1; okn h2c h3c h4c h5c h6c h1c || CK=0
CK1=1; okn h2c1 || CK1=0
CK2F=1; okn h3c2 || CK2F=0
echo "gate 1: defaults identical; CK=$CK CK1=$CK1 CK2F=$CK2F" >> $sum
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
  r t3k_$nm tp106 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
t3k b256 OWN_PROMPT_BLOCK=256
t3k b512px OWN_PROMPT_BLOCK=512 $PB
okn t3k_b256 t3k_b512px || { echo STOP_GATE2 >> $sum; exit 1; }
echo "gate 2: 3K traces identical" >> $sum
# ---- 3. plain speed alternated x2 (a = tp105 with the new defaults as env, b = tp106 defaults)
memwait; $W/run_exp.sh tg106 tp106 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
ARMS=("a|tp105|$PL OWN_FL=3 OWN_U3_NOPAIR=1 OWN_MT_EU_HEAVY=0" "b|tp106|$PL")
for rd in 1 2; do for k in "${ARMS[@]}"; do IFS='|' read -r name bin envs <<< "$k"; memwait; $W/run_exp.sh tg106 $bin "${name}_$rd|$envs|speed"; sed -i '/^DONE$/d' $sum; done; done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
fcheck "$tg"
# ---- 4. guessing (BEST + vocabulary): tp106 vs tp106 + CK2, code / analysis alternated x2; forms once; other prompts once
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5 $VOC"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 b=$2 n=$3; shift 3
  r $name $b $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt
  glog $D/$name-spec.txt $W/runs/tg105v/${n}_v1-spec.txt ${name}_vs_v1; }
for rd in 1 2; do for n in code analysis; do
  sp ${n}_b$rd tp106 $n $BEST
  [ $CK = 1 ] && sp ${n}_c$rd tp106 $n $BEST OWN_CK2=1
done; done
for n in code analysis; do
  [ $CK = 1 ] && [ $CK1 = 1 ] && sp ${n}_c1 tp106 $n $BEST OWN_CK2=1 OWN_CK2_FORMS=1
  [ $CK = 1 ] && [ $CK2F = 1 ] && sp ${n}_c2 tp106 $n $BEST OWN_CK2=1 OWN_CK2_FORMS=2
done
for n in prose docs ops; do sp ${n}_b1 tp106 $n $BEST; [ $CK = 1 ] && sp ${n}_c1 tp106 $n $BEST OWN_CK2=1; done
# ---- 5. 3K reads (256 answers): tp106 defaults at 256 and px-512
r p3k_b256 tp106 $p 256 4096 -1 $D/p3k_b256-ids.txt $PL OWN_PROMPT_BLOCK=256; same $D/p3k_b256-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_b256
r p3k_b512px tp106 $p 256 4096 -1 $D/p3k_b512px-ids.txt $PL OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1; same $D/p3k_b512px-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_b512px
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
