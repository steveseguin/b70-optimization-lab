#!/bin/bash
# tg105pt: the same tp104 binary after the reboot with iommu=pt (peer traffic no longer translated by the IOMMU).
# Exactness (traces), then speed against tg104's numbers from before the reboot, plus the store exchange
# (OWN_XPULL=0: pushes instead of loads for big slices; pushes ran ~1 GB/s per card with the IOMMU translating).
# Started by postboot-pt.sh after the probe and the peer benches.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg105pt
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
echo "cmdline: $(cat /proc/cmdline); card iommu domain: $(cat /sys/bus/pci/devices/0000:03:00.0/iommu_group/type)" >> $sum
SP=
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
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
AX="OWN_PAIR_G128=1 OWN_MT_PACE=1" # A (tp102) = tp104's defaults
OFF="OWN_PAIR_G128=0 OWN_MT_PACE=0 OWN_PB=0 OWN_ATT_WA=0"
R127="OWN_MT_PACE_ROLES=127"
PX="OWN_PX=1 OWN_PX_CHECK=1"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
PB="OWN_PX=1 OWN_PX_BIG=1 OWN_PX_CHECK=1"
W8="OWN_PX_WGS=16,16,16,16,8,8,16,16"; W4="OWN_PX_WGS=16,16,16,16,4,4,16,16"
# ---- 1. traces (tp104 against runs/ab1 and the 3K reference), loads and stores
L1=("h1|$T1" "h5|$T5" "h256|$TB OWN_PROMPT_BLOCK=256" "h5xp0|$T5 OWN_XPULL=0" "h256xp0|$TB OWN_PROMPT_BLOCK=256 OWN_XPULL=0")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh tg105pt tp104 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn h1 h5 h256 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
XP0=1; okn h5xp0 h256xp0 || XP0=0
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  memwait; echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  grep -h "OWN_PX_CHECK" $D/$name.log | tail -1 | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref
t3k() { local nm=$1; shift
  r t3k_$nm tp104 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
t3k b256 OWN_PROMPT_BLOCK=256
okn t3k_b256 || { echo STOP_GATE2 >> $sum; exit 1; }
t3k b512px OWN_PROMPT_BLOCK=512 $PB
[ $XP0 = 1 ] && t3k b256xp0 OWN_PROMPT_BLOCK=256 OWN_XPULL=0
okn t3k_b256xp0 || XP0=0
PXOK=1; okn t3k_b512px || PXOK=0
echo "gate 1: defaults identical; XP0=$XP0 PXOK=$PXOK" >> $sum
# ---- 2. plain speed (compare tg104c's b_1 and tg103), warm-up first; stores
memwait; $W/run_exp.sh tg105pt tp104 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for k in "b_1|$PL" "b_2|$PL"; do IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh tg105pt tp104 "$name|$envs|speed"; sed -i '/^DONE$/d' $sum; done
if [ $XP0 = 1 ]; then for k in "x0_1|$PL OWN_XPULL=0" "x0_2|$PL OWN_XPULL=0"; do IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh tg105pt tp104 "$name|$envs|speed"; sed -i '/^DONE$/d' $sum; done; fi
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
fcheck "$tg"
# ---- 3. 3K prompt reads (256 answers), alternated x2
for rd in 1 2; do
  for k in "base256_$rd|OWN_PROMPT_BLOCK=256" "px512_$rd|OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1" "x0b256_$rd|OWN_PROMPT_BLOCK=256 OWN_XPULL=0"; do
    IFS='|' read -r name envs <<< "$k"
    case $name in px*) [ $PXOK = 1 ] || continue;; x0*) [ $XP0 = 1 ] || continue;; esac
    r p3k_$name tp104 $p 256 4096 -1 $D/p3k_$name-ids.txt $PL $envs
    same $D/p3k_$name-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_$name
  done
done
# ---- 4. guessing (tp104 defaults), loads and stores
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 b=$2 n=$3; shift 3
  r $name $b $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
sp code_b tp104 code $BEST; glog $D/code_b-spec.txt $W/runs/tg100/code_w2_1-spec.txt code_b_vs_w2_1
sp analysis_b tp104 analysis $BEST; glog $D/analysis_b-spec.txt $W/runs/tg100/analysis_w2_1-spec.txt analysis_b_vs_w2_1
if [ $XP0 = 1 ]; then
  sp code_x0 tp104 code $BEST OWN_XPULL=0; glog $D/code_x0-spec.txt $W/runs/tg100/code_w2_1-spec.txt code_x0_vs_w2_1
  sp analysis_x0 tp104 analysis $BEST OWN_XPULL=0; glog $D/analysis_x0-spec.txt $W/runs/tg100/analysis_w2_1-spec.txt analysis_x0_vs_w2_1
fi
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|TRACE_DIFFERS\|IDS40_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
