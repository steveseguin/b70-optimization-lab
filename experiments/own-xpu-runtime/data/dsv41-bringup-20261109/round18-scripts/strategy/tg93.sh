#!/bin/bash
# tg93: gate for tp93 = tp92 + skn-1 (opt-in: OWN_MT_SKNORM=mask = block-step norms in the one-token fast forms,
# one work-group per token: 1 the 5120 norm, 2 the pre-norm fused with its SkDotsWM rows, 4 the q_a + kv norms, 8 the
# compressor pools; OWN_MT_SKNORM_MIN / _MAX (1 / 64, MAX for bits 1/2/16); OWN_MT_HCPP=1 HcPostPrePM without the 64-bit
# division). Runs after tune92 (cards). Coverage from skn/README.md "What the gate must cover".
# 1. prompt-1 traces with SKN=15 + HCPP at blocks 1 / 5 / 16 / 64 / 256, MAX=256 at 256, and the paths that change
#    which norm form runs (SKDOTS=0 RIDE=1, SKDOTS=4, DSPLIT=0, RIDE=0 SKDOTS=0, FIN_QB=0 DSPLIT=0) at 5 and 64
# 2. 3K traces with SKN at 64 / 128, and MAX=256 at 256
# 3. plain speed (one-token steps do not use SKN): tp92 / tp93 / tp93 + SKN, alternated twice
# 4. 3K read: tp93 / + SKN at 64, + SKN at 128, + SKN MAX=256 at 256, alternated twice
# 5. guessing: default, SKN, SKN with the mix split from 3 / 4 tokens (code, analysis x 2; prose; 3K)
# 6. card 2 kernel profile and a check timeline with SKN
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg93
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp93 build exit" $W/build-tp93.log 2>/dev/null; do sleep 10; done
grep -q "tp93 build exit 0" $W/build-tp93.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp93.log >> $sum
until grep -qE "ALLDONE|STOP" $W/runs/tune92/summary.txt 2>/dev/null; do sleep 20; done
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
SKN="OWN_MT_SKNORM=15 OWN_MT_HCPP=1"
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h1|$T1 $SKN" "h5|$T5 $SKN" "h16|$TB OWN_PROMPT_BLOCK=16 $SKN" "h64|$TB OWN_PROMPT_BLOCK=64 $SKN" \
         "h256|$TB OWN_PROMPT_BLOCK=256 $SKN" "h256max|$TB OWN_PROMPT_BLOCK=256 $SKN OWN_MT_SKNORM_MAX=256" \
         "h5sk0|$T5 $SKN OWN_MT_SKDOTS=0 OWN_MT_RIDE=1" "h64sk0|$TB OWN_PROMPT_BLOCK=64 $SKN OWN_MT_SKDOTS=0 OWN_MT_RIDE=1" \
         "h5sk4|$T5 $SKN OWN_MT_SKDOTS=4" "h64sk4|$TB OWN_PROMPT_BLOCK=64 $SKN OWN_MT_SKDOTS=4" \
         "h5ds0|$T5 $SKN OWN_MT_DSPLIT=0" "h64ds0|$TB OWN_PROMPT_BLOCK=64 $SKN OWN_MT_DSPLIT=0" \
         "h5r0|$T5 $SKN OWN_MT_RIDE=0 OWN_MT_SKDOTS=0" "h64r0|$TB OWN_PROMPT_BLOCK=64 $SKN OWN_MT_RIDE=0 OWN_MT_SKDOTS=0" \
         "h5fq0|$T5 $SKN OWN_MT_FIN_QB=0 OWN_MT_DSPLIT=0" "h64fq0|$TB OWN_PROMPT_BLOCK=64 $SKN OWN_MT_FIN_QB=0 OWN_MT_DSPLIT=0" \
         "h5m33|$T5 $SKN OWN_MT_DSPLIT_MIN=3 OWN_MT_SKDOTS_MIN=3"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg93 tp93 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
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
for k in "b64|OWN_PROMPT_BLOCK=64 $SKN" "b128|OWN_PROMPT_BLOCK=128 $SKN" "b256max|OWN_PROMPT_BLOCK=256 $SKN OWN_MT_SKNORM_MAX=256"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp93 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg93 tp93 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a92_$rd|92|" "d93_$rd|93|" "s93_$rd|93|$SKN"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg93 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "d93|93|" "skn|93|$SKN" "skn128|93|$SKN OWN_PROMPT_BLOCK=128" "skn256|93|$SKN OWN_PROMPT_BLOCK=256 OWN_MT_SKNORM_MAX=256"; do
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
  r $name tp93 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for rd in 1 2; do
  for n in code analysis; do
    sp ${n}_d93_$rd $n $BEST;                  glog $D/${n}_d93_$rd-spec.txt $W/runs/tg92/${n}_d92_1-spec.txt ${n}_d93_${rd}_vs_tg92
    sp ${n}_skn_$rd $n $BEST $SKN;             glog $D/${n}_skn_$rd-spec.txt $D/${n}_d93_$rd-spec.txt ${n}_skn_$rd
    sp ${n}_sk33_$rd $n $BEST $SKN OWN_MT_DSPLIT_MIN=3 OWN_MT_SKDOTS_MIN=3; glog $D/${n}_sk33_$rd-spec.txt $D/${n}_d93_$rd-spec.txt ${n}_sk33_$rd
    sp ${n}_sk44_$rd $n $BEST $SKN OWN_MT_DSPLIT_MIN=4 OWN_MT_SKDOTS_MIN=4; glog $D/${n}_sk44_$rd-spec.txt $D/${n}_d93_$rd-spec.txt ${n}_sk44_$rd
  done
done
for n in prose; do
  sp ${n}_d93 $n $BEST
  sp ${n}_skn $n $BEST $SKN
done
for v in d93 skn; do
  if [ $v = d93 ]; then envs=""; else envs="$SKN"; fi
  r p3k_spec_$v tp93 $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 20): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. card 2 kernel profile and a check timeline (default)
r gprof_ck tp93 $PP/code-ids.txt 256 4096 1 $D/gprof_ck-ids.txt $BEST $SKN OWN_GPROF=2 OWN_GPROF_CARD=2 OWN_GPROF_DECODE=1
r tl_ck tp93 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $SKN OWN_SPEC_LOG=$D/tl_ck-spec.txt OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
