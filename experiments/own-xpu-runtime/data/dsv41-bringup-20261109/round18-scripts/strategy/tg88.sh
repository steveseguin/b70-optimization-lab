#!/bin/bash
# tg88: gate for tp88 = tp87 (43605b0b2) + OWN_XPULL_GRF=128 by default + mtx256.patch (prompt blocks up to 256
# tokens; from 128 tokens expert groups of up to 16 slots, heaviest first) + opt-in: OWN_ENG_CQ (engram row copies
# on a copy queue), OWN_PRE_K (pre-mix weights by the broadcast launch), OWN_ATT_M (the faster attention forms in
# blocks), OWN_HEAD_CQ (a check's argmax readback on the copy queue after the draft's injection), OWN_SPEC_NGRAM
# (guesses copied from earlier text). SHORT six-card runs only (prompt 1, the 82 / 113-token prompts, the 3K document).
# 1. prompt-1 traces + 40 answers against runs/ab1; stop on any difference
# 2. 3K traces + 40 answers against gm64's tp84 blocks-of-16 trace; stop on any difference
# 3. prompt 1 speed, 128 answers: defaults / NEW alternated twice
# 4. the 3K read, 256 answers: blocks 64 / 256 / 256 cap 6 / 256 + NEW, alternated twice
# 5. guessing: code / analysis at blocks 16 and 256 (same counts), with NEW + OWN_HEAD_CQ (same counts), with the
#    lookup guesses (n = 3 up to 8, n = 4 up to 16); the 3K at 256 default / NEW + HEAD_CQ / lookup; per-round logs
# 6. timelines: one-token steps and checks with NEW (+ HEAD_CQ)
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg88
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "build exit" $W/build-tp88.log 2>/dev/null; do sleep 10; done
grep -q "build exit 0" $W/build-tp88.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp88.log >> $sum
SP=
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -x own_run_v41 > /dev/null || pgrep -f "own_run_v41_" > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
FB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_EU=6 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1 OWN_MT_W16=0"
NEW="OWN_ENG_CQ=1 OWN_PRE_K=1 OWN_ATT_M=1"
tg=$(date '+%Y-%m-%d %H:%M:%S')
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h16|$TB OWN_PROMPT_BLOCK=16" "h5|$T5" "h1|$T1" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" \
         "h1n|$T1 $NEW" "h16n|$TB OWN_PROMPT_BLOCK=16 $NEW" "h64n|$TB OWN_PROMPT_BLOCK=64 $NEW" "h5n|$T5 $NEW" \
         "h1x0|$T1 OWN_XPULL_GRF=0" "h256fb|$FB OWN_PROMPT_BLOCK=256" "h256eu0|$TB OWN_PROMPT_BLOCK=256 OWN_MT_EU=0"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg88 tp88 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $sum && { echo STOP_GATE1 >> $sum; exit 1; }
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|host io\|lookup guesses\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference
for k in "b256|OWN_PROMPT_BLOCK=256" "b200|OWN_PROMPT_BLOCK=200" "b129|OWN_PROMPT_BLOCK=129" "b128|OWN_PROMPT_BLOCK=128" \
         "b64|OWN_PROMPT_BLOCK=64" "b16|OWN_PROMPT_BLOCK=16" "b256cap6|OWN_PROMPT_BLOCK=256 OWN_MT_EU_BIG=0" \
         "b256asc|OWN_PROMPT_BLOCK=256 OWN_MT_EU_HEAVY=0" "b256eu0|OWN_PROMPT_BLOCK=256 OWN_MT_EU=0" \
         "b64n|OWN_PROMPT_BLOCK=64 $NEW" "b256n|OWN_PROMPT_BLOCK=256 $NEW"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp88 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
r t3k_fb256 tp88 $p 40 4096 1 $D/t3k_fb256-ids.txt $FB OWN_PROMPT_BLOCK=256 OWN_TRACE=$D/t3k_fb256.trc OWN_TRACE_STEPS=3
cmp -s $D/t3k_fb256.trc $REF.trc && echo "t3k_fb256 TRACE_IDENTICAL" >> $sum || echo "t3k_fb256 TRACE_DIFFERS" >> $sum
rm -f $D/t3k_fb256.trc
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1)
for rd in 1 2; do
  for k in "s_def$rd|" "s_new$rd|$NEW"; do
    IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg88 tp88 "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "b64|64|" "b256|256|" "b256cap6|256|OWN_MT_EU_BIG=0" "b256n|256|$NEW"; do
    IFS='|' read -r nm m extra <<< "$k"
    r p3k_${nm}_$rd tp88 $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL OWN_PROMPT_BLOCK=$m $extra
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 5. guessing
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
gk() { grep -o "[0-9]* of [0-9]* guesses kept" $D/$1.log; }
for n in code analysis; do
  for k in "q16|OWN_PROMPT_BLOCK=16" "q256|OWN_PROMPT_BLOCK=256" "qn|OWN_PROMPT_BLOCK=256 $NEW OWN_HEAD_CQ=1" \
           "ng3|OWN_PROMPT_BLOCK=256 OWN_SPEC_NGRAM=3 OWN_SPEC_NGRAM_MAX=8" "ng4|OWN_PROMPT_BLOCK=256 OWN_SPEC_NGRAM=4 OWN_SPEC_NGRAM_MAX=16"; do
    IFS='|' read -r v envs <<< "$k"
    r ${n}_$v tp88 $PP/$n-ids.txt 512 4096 1 $D/${n}_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/${n}_$v-spec.txt \
      OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
  done
  a=$(gk ${n}_q16); b=$(gk ${n}_q256); c=$(gk ${n}_qn)
  [ -n "$a" ] && [ "$a" = "$b" ] && [ "$a" = "$c" ] && echo "${n} GUESSES_SAME ($a)" >> $sum || echo "${n} GUESSES_DIFFER ($a / $b / $c)" >> $sum
done
for k in "spec256|OWN_PROMPT_BLOCK=256" "specn|OWN_PROMPT_BLOCK=256 $NEW OWN_HEAD_CQ=1" "specng3|OWN_PROMPT_BLOCK=256 OWN_SPEC_NGRAM=3 OWN_SPEC_NGRAM_MAX=8"; do
  IFS='|' read -r v envs <<< "$k"
  r p3k_$v tp88 $p 256 4096 -1 $D/p3k_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
done
a=$(gk p3k_spec256); b=$(gk p3k_specn)
[ -n "$a" ] && [ "$a" = "$b" ] && echo "p3k GUESSES_SAME ($a)" >> $sum || echo "p3k GUESSES_DIFFER ($a / $b)" >> $sum
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 13): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GUESSES_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. timelines (device clock): one-token steps 20-27 and checks 20-27 on the code prompt, with NEW
r tl_one tp88 $L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt 40 4096 -1 $D/tl_one-ids.txt \
  $PL $NEW OWN_TIMELINE=$D/tl_one.txt OWN_TIMELINE_STEPS=20-27
r tl_ck tp88 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $NEW OWN_HEAD_CQ=1 OWN_DSPARK=$DS OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
