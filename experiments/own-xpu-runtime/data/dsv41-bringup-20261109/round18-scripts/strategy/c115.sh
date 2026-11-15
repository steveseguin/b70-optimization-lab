#!/bin/bash
# c115 (2026-11-15): build tp115 and gate it in the STABLE MODE (owner 2026-11-15: incorporate Codex's workaround so
# kernel work can proceed reliably): OWN_PX_SERIAL=1 (tp115 default; stable.env too), six GPU root links Gen4 x16
# (stable/gen4.sh), BIOS 11.02, default power. tp115 = tp114 sources + defaults OWN_SKIP39=1, OWN_IDX_DSPLIT=3 (both
# gated exact in tg114 + its long-document resume), OWN_PX_SERIAL=1. Arms: def (tp115 defaults) / off (OWN_SKIP39=0
# OWN_IDX_DSPLIT=0, = tp114 serial). Speeds compare only within the stable mode. Holds six.active from start to end.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/c115
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
g=$(cat $W/six.active 2>/dev/null); case "$g" in ""|extended-40-20261114T2326|c115) ;; *) echo "STOP six.active held by $g" >> $sum; exit 1;; esac
echo c115 > $W/six.active   # (took over Codex's stability guard extended-40-20261114T2326, 2026-11-15; held to the end)
trap 'rm -f $W/six.active' EXIT
pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null && { echo "STOP engine running" >> $sum; exit 1; }
source $W/stable/stable.env
echo "stable mode: $($W/stable/preflight.sh 2>&1 | tail -1)" >> $sum
$W/stable/preflight.sh > /dev/null || { echo STOP_PREFLIGHT >> $sum; exit 1; }
[ -x $W/own_run_v41_tp115 ] && grep -q "tp115 build exit 0" $W/build-tp115.log 2>/dev/null || $W/build115.sh
grep -q "tp115 build exit 0" $W/build-tp115.log || { echo STOP_BUILD >> $sum; exit 1; }
grep "tp115 build exit" $W/build-tp115.log | tail -1 >> $sum
$W/stable/preflight.sh > /dev/null || { echo STOP_PREFLIGHT >> $sum; exit 1; }
SP= # gpu_sampler off since 2026-11-12 19:20: its 120 card-register reads per second are CPU waits on the cards (host-reset victims)
gap() { echo "gap $(date +%T)" >> $sum; sleep 10; $W/stable/preflight.sh > /dev/null || { echo STOP_PREFLIGHT >> $sum; exit 1; }; }
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




P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
SK="OWN_SKIP39=1"; SC="OWN_SKIP39_CHECK=1"; IX="OWN_IDX_DSPLIT=3"; IXL="OWN_IDX_DSPLIT_MIN=513"; IXC="OWN_IDX_DSPLIT_CHECK=1"
ON="$SK $IX"
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref
[ -s $W/prompts/p3080-ids.txt ] || head -n 3080 $p > $W/prompts/p3080-ids.txt
p38=$W/prompts/p3080-ids.txt; p10=$W/prompts/p10k-ids.txt
# check-line verdicts of a log: SKIP39_CHECK ALL SAME (if present / required), no px BAD, every DSPLIT line "0 differ"
ck() { local name=$1 need=$2 f=$D/$1.log ok=1
  if [ "$need" = s ] || [ "$need" = sx ]; then grep -q "OWN_SKIP39_CHECK: .*-> ALL SAME" $f || ok=0; fi
  if [ "$need" = x ] || [ "$need" = sx ]; then grep -q "OWN_IDX_DSPLIT=.*differ$" $f || ok=0; grep "OWN_IDX_DSPLIT=.*differ$" $f | grep -qv " 0 differ$" && ok=0; fi
  grep -q "OWN_PX_CHECK: block .* BAD" $f && ok=0
  grep -h "OWN_SKIP39\|OWN_IDX_DSPLIT=.*card 0:\|OWN_PX_CHECK: [0-9]" $f | sed "s/^/$name: /" >> $sum
  [ $ok = 1 ] && echo "$name CHECK_OK" >> $sum || echo "$name CHECK_BAD" >> $sum; }
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
t3k() { local nm=$1; shift
  r t3k_$nm tp114 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
okc() { for n in "$@"; do grep -q "^$n CHECK_OK" $sum || return 1; done; }

p=$W/prompts/p3k-ids.txt; p10=$W/prompts/p10k-ids.txt
REF=$W/runs/gm64/t3k_ref
OFF2="OWN_SKIP39=0 OWN_IDX_DSPLIT=0"
P5="OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1"
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  memwait; echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|rror\|timed out\|exceeds\|MISMATCH\|OWN_SKIP39: layer\|OWN_IDX_DSPLIT=.*card 0:" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
t3k() { local nm=$1; shift
  r t3k_$nm tp115 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
# ---- 1. traces: prompt 1 (defaults) vs runs/ab1, 3K px-512 defaults and switches off vs gm64
for k in "h1|$T1" "h5|$T5" "h16|$TB OWN_PROMPT_BLOCK=16" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256"; do
  IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh c115 tp115 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum; fcheck "$tg"
done
t3k def OWN_PROMPT_BLOCK=512 $PB
t3k off OWN_PROMPT_BLOCK=512 $PB $OFF2
okn h1 h5 h16 h64 h256 t3k_def t3k_off || { echo STOP_GATE1 >> $sum; exit 1; }
grep -q "OWN_SKIP39: layer .* ran only its kept key rows in [1-9]" $D/t3k_def.log || { echo "STOP_GATE1 (skip39 not on by default)" >> $sum; exit 1; }
echo "gate 1: traces identical (defaults: serial + skip39 + dsplit; and switches off)" >> $sum
gap
# ---- 2. plain speed (prompt 1, 128 answers) x2
memwait; $W/run_exp.sh c115 tp115 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do memwait; $W/run_exp.sh c115 tp115 "plain_$rd|$PL|speed"; sed -i '/^DONE$/d' $sum; done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
gap
# ---- 3. 3K reads def / off alternated x2 (256 answers vs e52), 10K def / off (64 vs tg107)
for rd in 1 2; do for k in "def|" "off|$OFF2"; do IFS='|' read -r nm envs <<< "$k"
  r p3k_${nm}_$rd tp115 $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $P5 $envs; same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
done; done
for k in "def|" "off|$OFF2"; do IFS='|' read -r nm envs <<< "$k"
  r p10k_$nm tp115 $p10 64 16384 -1 $D/p10k_$nm-ids.txt $PL $P5 $envs; same $D/p10k_$nm-ids.txt $W/runs/tg107/p10k_bcs-ids.txt 64 p10k_$nm; done
grep -q "ANSWER.*DIFFERS" $sum && { echo STOP_ANSWERS >> $sum; exit 1; }
gap
# ---- 4. guessing (BEST + vocabulary) code + analysis, defaults (GLOG vs tg105v, SAME AS plain e57)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5 $VOC"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
for n in code analysis; do
  r ${n}_def tp115 $PP/$n-ids.txt 512 4096 1 $D/${n}_def-ids.txt $BEST OWN_SPEC_LOG=$D/${n}_def-spec.txt OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt
  glog $D/${n}_def-spec.txt $W/runs/tg105v/${n}_v1-spec.txt ${n}_def_vs_v1; done
gap
# ---- 5. long documents def / off (256 answers vs e82), then guessing after x95k (defaults)
for n in x34k x95k; do
  px=$W/prompts/xl/$n-ids.txt; mx=$(( ( $(wc -l < $px) + 256 + 1023 ) / 1024 * 1024 ))
  for k in "def|" "off|$OFF2"; do IFS='|' read -r nm envs <<< "$k"
    r ${n}_$nm tp115 $px 256 $mx -1 $D/${n}_$nm-ids.txt $PL $P5 $envs; same $D/${n}_$nm-ids.txt $W/runs/e82/${n}_plain-ids.txt 256 ${n}_$nm
  done
  gap
done
px=$W/prompts/xl/x95k-ids.txt; mx=$(( ( $(wc -l < $px) + 256 + 1023 ) / 1024 * 1024 ))
r s95_def tp115 $px 256 $mx -1 $D/s95_def-ids.txt $PL $P5 $SPEC OWN_SPEC_TAU=0.5 $VOC OWN_SPEC_LOG=$D/s95_def-spec.txt OWN_VERIFY_REF=$W/runs/e82/x95k_plain-ids.txt
same $D/s95_def-ids.txt $W/runs/e82/x95k_plain-ids.txt 256 s95_def
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER\|TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo "SOME_DIFFER" >> $sum; echo ALLDONE >> $sum; exit 0; }
echo ALLDONE >> $sum
