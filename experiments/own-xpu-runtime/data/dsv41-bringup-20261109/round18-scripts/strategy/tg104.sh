#!/bin/bash
# tg104: prompt-centred gate for tp104 = tp103 + px-512 (OWN_PX_BIG=1: blocks up to 512 as two halves of 256, kernels
# never see more than 256 tokens) + px-move (OWN_PX_MOVE 0-3, OWN_PX_WGS per-pull work-groups), all opt-in (pb256).
# Speed is judged only by unprofiled runs alternated (profiled queues change two-queue overlap: pb256 engbench).
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg104
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
until grep -q "tp104 build exit" $W/build-tp104.log 2>/dev/null; do sleep 10; done
grep -q "tp104 build exit 0" $W/build-tp104.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -n 1 $W/build-tp104.log >> $sum
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
# ---- 1. prompt-1 traces (tp104 against runs/ab1)
L1=("h1|$T1" "h5|$T5" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" "h4|$TM OWN_PROMPT_BLOCK=4" \
    "h36px|$TB OWN_PROMPT_BLOCK=36 OWN_PX=1 OWN_PX_CHECK=1 OWN_PX_MIN=16" \
    "h512px|$TB OWN_PROMPT_BLOCK=512 $PB OWN_PX_MIN=16" "h36mv|$TB OWN_PROMPT_BLOCK=36 OWN_PX=1 OWN_PX_MIN=16 OWN_PX_MOVE=3")
for k in "${L1[@]}"; do
  IFS='|' read -r name envs <<< "$k"; memwait; $W/run_exp.sh tg104 tp104 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
  fcheck "$tg"
done
okn h1 h5 h64 h256 h4 || { echo STOP_GATE1_DEFAULTS >> $sum; exit 1; }
PXOK=1; okn h36px h512px h36mv || PXOK=0
echo "gate 1: defaults identical; PXOK=$PXOK" >> $sum
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  memwait; echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|free after\|rows per card\|heads per card\|OWN_PX\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | grep -v "blocks as halves, 0 bad" | sed "s/^/$name: /" >> $sum
  grep -h "OWN_PX_CHECK" $D/$name.log | tail -1 | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference (tp104)
t3k() { local nm=$1; shift
  r t3k_$nm tp104 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB "$@" OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc; }
t3k b256 OWN_PROMPT_BLOCK=256
okn t3k_b256 || { echo STOP_GATE2 >> $sum; exit 1; }
if [ $PXOK = 1 ]; then
  t3k b512px1 OWN_PROMPT_BLOCK=512 $PB
  t3k b512px2 OWN_PROMPT_BLOCK=512 $PB
  t3k b512pxs OWN_PROMPT_BLOCK=512 $PB OWN_PX_SERIAL=1
  t3k b301 OWN_PROMPT_BLOCK=301 $PB
  t3k b300 OWN_PROMPT_BLOCK=300 $PB
  t3k b256big OWN_PROMPT_BLOCK=256 $PB
  t3k b512w8 OWN_PROMPT_BLOCK=512 $PB $W8
  t3k b512w4 OWN_PROMPT_BLOCK=512 $PB $W4
  t3k b512mv OWN_PROMPT_BLOCK=512 $PB OWN_PX_MOVE=3
  okn t3k_b512px1 t3k_b512px2 t3k_b512pxs t3k_b301 t3k_b300 t3k_b256big t3k_b512w8 t3k_b512w4 t3k_b512mv || PXOK=0
  grep -E "OWN_PX_CHECK" $sum | grep -qv " 0 bad" && { echo "PX_CHECK reported bad blocks" >> $sum; PXOK=0; }
fi
echo "gate 2: PXOK=$PXOK" >> $sum
# ---- 3. plain speed check (decode unchanged), warm-up first
memwait; $W/run_exp.sh tg104 tp104 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for k in "a_1|tp103" "b_1|tp104"; do IFS='|' read -r name bin <<< "$k"; memwait; $W/run_exp.sh tg104 $bin "$name|$PL|speed"; sed -i '/^DONE$/d' $sum; done
grep -q "SPEED128_DIFFER" $sum && { echo STOP_SPEED >> $sum; exit 1; }
fcheck "$tg"
# ---- 4. 3K prompt reads (whole times, 256 answers), alternated x2
for rd in 1 2; do
  for k in "base256_$rd|OWN_PROMPT_BLOCK=256" "px256_$rd|OWN_PROMPT_BLOCK=256 OWN_PX=1" "px512_$rd|OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1" \
           "px512s_$rd|OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 OWN_PX_SERIAL=1" "px512w8_$rd|OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 $W8" \
           "px512w4_$rd|OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 $W4"; do
    IFS='|' read -r name envs <<< "$k"
    case $name in px*) [ $PXOK = 1 ] || continue;; esac
    r p3k_$name tp104 $p 256 4096 -1 $D/p3k_$name-ids.txt $PL $envs
    same $D/p3k_$name-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_$name
  done
done
if [ $PXOK = 1 ]; then
  r p3k_px512mv tp104 $p 256 4096 -1 $D/p3k_px512mv-ids.txt $PL OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 OWN_PX_MOVE=3
  same $D/p3k_px512mv-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_px512mv
fi
# ---- 5. guessing sanity (tp104 defaults) + after a 3K prompt read at 512 with the overlap
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
r p3k_spec_b tp104 $p 256 4096 -1 $D/p3k_spec_b-ids.txt $BEST OWN_PROMPT_BLOCK=256 OWN_SPEC_LOG=$D/p3k_spec_b-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
if [ $PXOK = 1 ]; then
  r p3k_spec_bpx tp104 $p 256 4096 -1 $D/p3k_spec_bpx-ids.txt $BEST OWN_PROMPT_BLOCK=512 OWN_PX=1 OWN_PX_BIG=1 OWN_SPEC_LOG=$D/p3k_spec_bpx-spec.txt OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
  glog $D/p3k_spec_bpx-spec.txt $D/p3k_spec_b-spec.txt p3k_spec_bpx_vs_b
fi
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
