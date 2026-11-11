#!/bin/bash
# tg92: gate for tp92 = tp91 with the tg91 winners on by default: OWN_MT_DSPLIT=1 + OWN_MT_SKDOTS=8 from 2 tokens on
# (prompt item C + the one-token dot rows in blocks; also in checks), OWN_DR_WS=1 + OWN_DR_ANCHOR_ARG=1 (the draft).
# OWN_DR_VOCAB stays opt-in, TAU 0.5. Also tested here as switches: the check head split (OWN_TP_HEADS_MIN=4, tune91)
# (OWN_TP_HEADS_MIN=3; tune91: +1.2 %) and 3K prompt blocks of 32 / 128. SHORT six-card runs only (prompt 1, the guessing prompts, the 3K document).
# 1. prompt-1 traces + 40 answers against runs/ab1 (defaults at 1 / 5 / 16 / 64 / 256; the new defaults off; head split)
# 2. 3K traces + 40 answers against gm64's tp84 trace (64 / 256 / 32 / 128, the new defaults off at 64)
# 3. prompt 1 speed, 128 answers: tp91 / tp92 alternated twice
# 4. the 3K read, 256 answers: tp91 + DS SK (same settings) / tp92 at 32 / 64 / 128, alternated twice
# 5. guessing: tp92 default x2 (guess logs equal to tg91's d91), vocabulary list, head split 4; prose; 3K
# 6. card 2 kernel profile and a check timeline (default)
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg92
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp92 build exit" $W/build-tp92.log 2>/dev/null; do sleep 10; done
grep -q "tp92 build exit 0" $W/build-tp92.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -2 $W/build-tp92.log >> $sum
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
OFF="OWN_MT_DSPLIT=0 OWN_MT_SKDOTS=0"
N91="OWN_MT_DSPLIT=1 OWN_MT_DSPLIT_MIN=2 OWN_MT_SKDOTS=8 OWN_MT_SKDOTS_MIN=2 OWN_DR_WS=1 OWN_DR_ANCHOR_ARG=1" # tp91 + tg91's winners
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h1|$T1" "h5|$T5" "h16|$TB OWN_PROMPT_BLOCK=16" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" \
         "h5off|$T5 $OFF" "h64off|$TB OWN_PROMPT_BLOCK=64 $OFF" "h64ds0|$TB OWN_PROMPT_BLOCK=64 OWN_MT_DSPLIT=0" \
         "h64sk0|$TB OWN_PROMPT_BLOCK=64 OWN_MT_SKDOTS=0" "h5hm3|$T5 OWN_TP_HEADS_MIN=3" "h5hm4|$T5 OWN_TP_HEADS_MIN=4" "h5hm2|$T5 OWN_TP_HEADS_MIN=2" \
         "h32|$TB OWN_PROMPT_BLOCK=32" "h128|$TB OWN_PROMPT_BLOCK=128"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg92 tp92 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
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
for k in "b64|OWN_PROMPT_BLOCK=64" "b256|OWN_PROMPT_BLOCK=256" "b32|OWN_PROMPT_BLOCK=32" "b128|OWN_PROMPT_BLOCK=128" \
         "b64off|OWN_PROMPT_BLOCK=64 $OFF"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp92 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg92 tp92 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a91_$rd|91|$N91" "d92_$rd|92|"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg92 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "a91|91|$N91" "d92|92|" "b32|92|OWN_PROMPT_BLOCK=32" "b128|92|OWN_PROMPT_BLOCK=128"; do
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
  r $name tp92 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d92_$rd $n $BEST;                     glog $D/${n}_d92_$rd-spec.txt $W/runs/tg91/${n}_d91-spec.txt ${n}_d92_${rd}_vs_tg91
    sp ${n}_hm3_$rd $n $BEST OWN_TP_HEADS_MIN=3;  glog $D/${n}_hm3_$rd-spec.txt $D/${n}_d92_$rd-spec.txt ${n}_hm3_$rd
    sp ${n}_voc_$rd $n $BEST $VOC
    sp ${n}_vh3_$rd $n $BEST $VOC OWN_TP_HEADS_MIN=3
  done
done
for n in prose; do
  sp ${n}_d92 $n $BEST
  sp ${n}_voc $n $BEST $VOC
done
for v in d92 voc; do
  if [ $v = d92 ]; then envs=""; else envs="$VOC"; fi
  r p3k_spec_$v tp92 $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 20): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. card 2 kernel profile and a check timeline (default)
r gprof_ck tp92 $PP/code-ids.txt 256 4096 1 $D/gprof_ck-ids.txt $BEST OWN_GPROF=2 OWN_GPROF_CARD=2 OWN_GPROF_DECODE=1
r tl_ck tp92 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
