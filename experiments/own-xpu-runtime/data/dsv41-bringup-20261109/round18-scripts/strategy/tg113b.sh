#!/bin/bash
# tg113b (2026-11-14 10:30, after the 02:03 host reset that cut tg113 at t3k_c1; gate 1 + t3k_b512 / b256 passed
# in tg113; ALL CARDS NOW AT 175 W (owner plan: 200 W did not stop the resets)). tg113: tp113 = tp112 + prt-1 (OWN_PRT default 3: prompt router + q_a/kv split by tokens) + rux7-1
# (OWN_RUX7 default 1: layer 0's Q2_K prompt down form). ALL CARDS CAPPED AT 200 W (owner test since 2026-11-13 20:44).
# Gate: traces (defaults; PRT/RUX7 off), 3K traces (defaults + two cap profiles), plain tp112 / tp113, guessing once,
# 3K reads tp112 / tp113 / C0 / C1 / C2 alternated x2, 10K, x34k + x95k (vs e82). Cap profiles (card 3 = 0000:83 is the
# slow card under the cap, round19-tlpx112 / hl112): C0 = token weights only, C1 / C2 = + a lighter head layout.
# Speed only from unprofiled runs alternated.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg113b
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
until grep -q "tp113 build exit [0-8]" $W/build-tp113.log 2>/dev/null; do sleep 10; done
grep -q "tp113 build exit 0" $W/build-tp113.log || { echo STOP_BUILD >> $sum; exit 1; }
grep "tp113 build exit" $W/build-tp113.log | tail -1 >> $sum
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



# ---- 1. prompt-1 traces (tp113 against runs/ab1): defaults (PRT 3, RUX7 1), then both off at 64 / 256 (= tp112 path)
X0="OWN_PRT=0 OWN_RUX7=0"
echo "gate 1: passed in tg113 (defaults + PRT/RUX7 off identical)" >> $sum
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
C0="OWN_PRT_W=3,3,2,0,4,4"
C1="OWN_TP_HEADS=3,3,3,2,3,2 OWN_TP_HEADS_MIN=16 OWN_PRT_W=3,3,3,0,3,4"
C2="OWN_TP_HEADS=3,3,2,2,3,3 OWN_TP_HEADS_MIN=16 OWN_PRT_W=3,3,4,0,3,3"
t3k() { local nm=$1; shift
  r t3k_$nm tp113 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
t3k c1 OWN_PROMPT_BLOCK=512 $PB $C1
t3k c2 OWN_PROMPT_BLOCK=512 $PB $C2
okn t3k_c1 t3k_c2 || { echo STOP_GATE2 >> $sum; exit 1; }
echo "gate 2: 3K traces identical (b512 / b256 in tg113, c1 / c2 here)" >> $sum
gap
# ---- 3. plain speed alternated x2: a = tp112, b = tp113 (no change expected: prt / rux7 are prompt-only)
memwait; $W/run_exp.sh tg113b tp113 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
ARMS=("a|tp112|$PL" "b|tp113|$PL")
for rd in 1 2; do for k in "${ARMS[@]}"; do IFS='|' read -r name bin envs <<< "$k"; memwait; $W/run_exp.sh tg113b $bin "${name}_$rd|$envs|speed"; sed -i '/^DONE$/d' $sum; done; done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
fcheck "$tg"
gap
# ---- 4. guessing (BEST + vocabulary) on tp113 defaults (tg112 at 200 W: code 152.86, analysis 169.70), code and analysis once (tg110: code 157.3-158.1, analysis 174.8-176.0)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5 $VOC"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 b=$2 n=$3; shift 3
  r $name $b $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt
  glog $D/$name-spec.txt $W/runs/tg105v/${n}_v1-spec.txt ${name}_vs_v1; }
for n in code analysis; do sp ${n}_b1 tp113 $n $BEST; done
gap
# ---- 5. 3K reads (256 answers) tp112 / tp113 / C0 / C1 / C2 alternated x2, 10K (px-512, copy engine)
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
A5=("tp112|tp112|" "tp113|tp113|" "c0|tp113|$C0" "c1|tp113|$C1" "c2|tp113|$C2")
for rd in 1 2; do for k in "${A5[@]}"; do IFS='|' read -r nm b envs <<< "$k"
  r p3k_${nm}_$rd $b $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $P5 $envs; same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
done; done
p10=$W/prompts/p10k-ids.txt
for k in "tp113|tp113|" "c1|tp113|$C1" "tp112|tp112|"; do IFS='|' read -r nm b envs <<< "$k"
  r p10k_$nm $b $p10 64 16384 -1 $D/p10k_$nm-ids.txt $PL $P5 $envs; same $D/p10k_$nm-ids.txt $W/runs/tg107/p10k_bcs-ids.txt 64 p10k_$nm; done
gap
# ---- 6. long documents on tp113 and tp113 + C1 (256 answers vs e82; tg112 at 200 W: x34k 56.06 s, x95k 162.42 s)
for n in x34k x95k; do
  px=$W/prompts/xl/$n-ids.txt; mx=$(( ( $(wc -l < $px) + 256 + 1023 ) / 1024 * 1024 ))
  for k in "tp113|" "c1|$C1"; do IFS='|' read -r nm envs <<< "$k"
    r ${n}_$nm tp113 $px 256 $mx -1 $D/${n}_$nm-ids.txt $PL $P5 $envs; same $D/${n}_$nm-ids.txt $W/runs/e82/${n}_plain-ids.txt 256 ${n}_$nm
  done
  [ $n = x34k ] && gap
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER\|TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo "SOME_DIFFER" >> $sum; echo ALLDONE >> $sum; exit 0; }
echo ALLDONE >> $sum
