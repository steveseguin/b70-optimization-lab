#!/bin/bash
# tg103: gate for tp103 = tp102 + px-1b (the halves' fused-router base, pb256) + OWN_TIMELINE_PROMPT (pb256) + xperm-3
# compiled in (IQ2_XXS / IQ3_XXS table copy) + pace-2 (OWN_MT_PACE_ROLES 8/16/32/64, opt-in) + defaults: G128 and
# pace-1 (OWN_MT_PACE mask 0x1f). A = tp102 with OWN_PAIR_G128=1 OWN_MT_PACE=1 (= tp103's defaults), B = tp103.
# Stops at the first fault line or a trace difference in the defaults; a PX or pace-2 difference only skips its speed
# arms. Waits for 7 GiB of free host memory before each run.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg103
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
until grep -q "tp103 build exit" $W/build-tp103.log 2>/dev/null; do sleep 10; done
grep -q "tp103 build exit 0" $W/build-tp103.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp103.log >> $sum
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
AX="OWN_PAIR_G128=1 OWN_MT_PACE=1" # A (tp102) = tp103's defaults
OFF="OWN_PAIR_G128=0 OWN_MT_PACE=0 OWN_PB=0 OWN_ATT_WA=0"
R127="OWN_MT_PACE_ROLES=127"
PX="OWN_PX=1 OWN_PX_CHECK=1"
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
okn() { for n in "$@"; do grep -q "^$n TRACE_IDENTICAL" $sum && grep -q "^$n IDS40_SAME" $sum || return 1; done; }
# ---- 1. prompt-1 traces (tp103 against runs/ab1)
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" "h4|$TM OWN_PROMPT_BLOCK=4" "h6|$TM OWN_PROMPT_BLOCK=6" \
    "h128|$TB OWN_PROMPT_BLOCK=128" "h256|$TB OWN_PROMPT_BLOCK=256" "h2|$TM OWN_PROMPT_BLOCK=2" "h3|$TM OWN_PROMPT_BLOCK=3" \
    "h5off|$T5 $OFF" "h1g0|$T1 OWN_PAIR_G128=0" \
    "h2r|$TM OWN_PROMPT_BLOCK=2 $R127" "h3r|$TM OWN_PROMPT_BLOCK=3 $R127" "h4r|$TM OWN_PROMPT_BLOCK=4 $R127" \
    "h5r|$T5 $R127" "h6r|$TM OWN_PROMPT_BLOCK=6 $R127" \
    "h36px|$TB OWN_PROMPT_BLOCK=36 $PX OWN_PX_MIN=16" "h36pxs|$TB OWN_PROMPT_BLOCK=36 $PX OWN_PX_MIN=16 OWN_PX_SERIAL=1")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh tg103 tp103 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn h1 h5 h64 h4 h6 h128 h256 h2 h3 h5off h1g0 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
ROK=1; okn h2r h3r h4r h5r h6r || ROK=0
PXOK=1; okn h36px h36pxs || PXOK=0
echo "gate 1: defaults identical; pace-2 ROK=$ROK; PX prompt-1 PXOK=$PXOK" >> $sum
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  memwait; echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|lookup guesses\|host io\|rows per card\|heads per card\|OWN_PX_CHECK\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference (tp103)
t3k() { local nm=$1; shift
  r t3k_$nm tp103 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
t3k b64 OWN_PROMPT_BLOCK=64
t3k b256 OWN_PROMPT_BLOCK=256
okn t3k_b64 t3k_b256 || { echo STOP_GATE2 >> $sum; exit 1; }
[ $ROK = 1 ] && t3k b256r OWN_PROMPT_BLOCK=256 $R127
for i in 1 2 3; do t3k b256px$i OWN_PROMPT_BLOCK=256 $PX; done
t3k b256pxs OWN_PROMPT_BLOCK=256 $PX OWN_PX_SERIAL=1
t3k b128px OWN_PROMPT_BLOCK=128 $PX OWN_PX_MIN=64
t3k b250px OWN_PROMPT_BLOCK=250 $PX OWN_PX_MIN=64
t3k b256pxw OWN_PROMPT_BLOCK=256 $PX OWN_PX_WG=32
okn t3k_b256px1 t3k_b256px2 t3k_b256px3 t3k_b256pxs t3k_b128px t3k_b250px t3k_b256pxw || PXOK=0
grep -E "^t3k_.*OWN_PX_CHECK" $sum | grep -v " 0 bad" | grep -q . && { echo "PX_CHECK reported bad blocks" >> $sum; PXOK=0; }
[ $ROK = 1 ] && { okn t3k_b256r || ROK=0; }
echo "gate 2: identical; PXOK=$PXOK ROK=$ROK" >> $sum
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1), warm-up first, A / B alternated
memwait; $W/run_exp.sh tg103 tp103 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a_$rd|tp102|$AX" "b_$rd|tp103|"; do
    IFS='|' read -r name bin envs <<< "$k"
    memwait; $W/run_exp.sh tg103 $bin "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. 3K prompt reads (whole times, 256 answers) at 256: base / PX / PX serial / PX WG32 alternated x2, base 128 once
for rd in 1 2; do
  for k in "p3k_base_$rd|" "p3k_px_$rd|OWN_PX=1" "p3k_pxs_$rd|OWN_PX=1 OWN_PX_SERIAL=1" "p3k_pxw_$rd|OWN_PX=1 OWN_PX_WG=32"; do
    IFS='|' read -r name envs <<< "$k"
    case $name in p3k_px*) [ $PXOK = 1 ] || continue;; esac
    r $name tp103 $p 256 4096 -1 $D/$name-ids.txt $PL OWN_PROMPT_BLOCK=256 $envs
    same $D/$name-ids.txt $W/runs/e52/p3kplain-ids.txt 256 $name
  done
done
r p3k_b128 tp103 $p 256 4096 -1 $D/p3k_b128-ids.txt $PL OWN_PROMPT_BLOCK=128
same $D/p3k_b128-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_b128
r p3k_a256 tp102 $p 256 4096 -1 $D/p3k_a256-ids.txt $PL OWN_PROMPT_BLOCK=256 $AX
same $D/p3k_a256-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_a256
# ---- 5. prompt timelines (blocks 3-4 of the 3K read; profiling on, not speed numbers)
for k in "tlp_base|" "tlp_px|OWN_PX=1" "tlp_pxs|OWN_PX=1 OWN_PX_SERIAL=1"; do
  IFS='|' read -r name envs <<< "$k"
  case $name in tlp_px*) [ $PXOK = 1 ] || continue;; esac
  r $name tp103 $p 8 4096 -1 $D/$name-ids.txt $PL OWN_PROMPT_BLOCK=256 $envs OWN_TIMELINE=$D/$name.txt OWN_TIMELINE_PROMPT=3-4
done
# ---- 6. guessing (prompt blocks of 64), A / B alternated; B with pace-2 (R127) when ROK
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
glog() { cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $1) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $2) && echo "$3 GLOG_SAME" >> $sum || echo "$3 GLOG_DIFFER" >> $sum; }
sp() { local name=$1 b=$2 n=$3; shift 3
  r $name $b $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
T100=$W/runs/tg100
BR=""; [ $ROK = 1 ] && BR="$R127"
for rd in 1 2; do
  for b in a b c; do
    case $b in a) bin=tp102; e="$AX";; b) bin=tp103; e="";; c) [ $ROK = 1 ] || continue; bin=tp103; e="$R127";; esac
    sp code_${b}_$rd $bin code $BEST $e; glog $D/code_${b}_$rd-spec.txt $T100/code_w2_1-spec.txt code_${b}_${rd}_vs_w2_1
    sp analysis_${b}_$rd $bin analysis $BEST $e; glog $D/analysis_${b}_$rd-spec.txt $T100/analysis_w2_1-spec.txt analysis_${b}_${rd}_vs_w2_1
  done
done
for b in a b; do
  if [ $b = a ]; then bin=tp102; e="$AX"; else bin=tp103; e="$BR"; fi
  sp prose_${b} $bin prose $BEST $e
  r p3k_spec_${b} $bin $p 256 4096 -1 $D/p3k_spec_${b}-ids.txt $BEST $e OWN_PROMPT_BLOCK=256 OWN_SPEC_LOG=$D/p3k_spec_${b}-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
sp code_bvoc tp103 code $BEST $BR $VOC
sp analysis_bvoc tp103 analysis $BEST $BR $VOC
sp code_bt40 tp103 code $PL $SPEC OWN_SPEC_TAU=0.4 $BR $VOC
sp analysis_bt40 tp103 analysis $PL $SPEC OWN_SPEC_TAU=0.4 $BR $VOC
if [ $PXOK = 1 ]; then
  r p3k_spec_bpx tp103 $p 256 4096 -1 $D/p3k_spec_bpx-ids.txt $BEST $BR OWN_PROMPT_BLOCK=256 OWN_PX=1 OWN_SPEC_LOG=$D/p3k_spec_bpx-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
  glog $D/p3k_spec_bpx-spec.txt $D/p3k_spec_b-spec.txt p3k_spec_bpx_vs_b
fi
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
# ---- 7. timelines: one-token (B) and checks (B with pace-2 when ROK)
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
r tl_one tp103 $P1 64 4096 -1 $D/tl_one-ids.txt $PL OWN_TIMELINE=$D/tl_one.txt
r tl_ck tp103 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $BR OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
