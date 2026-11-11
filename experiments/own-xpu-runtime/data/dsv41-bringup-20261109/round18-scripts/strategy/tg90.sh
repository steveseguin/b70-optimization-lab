#!/bin/bash
# tg90: gate for tp90 = tp89 with OWN_SMALLK=1 OWN_SMALLK_DOTS=8 on by default (tg89: 99.6 tok/s) + ckpath-1.patch
# (the check path's fixed cost; every switch off by default) + OWN_XL2 moved to its own queue (pfq; opt-in) +
# routed-r4.patch (r3's decode in the expert-major RoutedU kernels of checks and prompt blocks; replaces them) +
# ws.patch (OWN_MT_WS=1, opt-in: dense rows decoded once per token group, per (matrix, M) where the bench won).
# Switches (ckpath README): OWN_CK1 (a zero-guess check runs the plain one-token step + the draft's own rows),
# OWN_RING_ONE (43 ring commits in one launch), OWN_DR_NOWAIT (the draft's embed does not wait), OWN_MT_KVPAIR
# (q_a + kv rows in one launch), OWN_MT_FIN_QB (attention mix finish in q_b's launch), OWN_MT_RIDE_MIN=m and
# OWN_MT_EU_MIN=m (the riding dots / expert-major groups only for blocks of >= m tokens).
# SHORT six-card runs only (prompt 1, the 82 / 113-token prompts, the 3K document).
# 1. prompt-1 traces + 40 answers against runs/ab1 (defaults; and the block switches at 5 / 16 / 64 / 256 tokens)
# 2. 3K traces + 40 answers against gm64's tp84 trace (blocks of 64 / 256, default and block switches)
# 3. prompt 1 speed, 128 answers: tp89 + SK / tp90 default / XL2 on its own queue / host threads poll 300 us
#    before sleeping (OWN_TP_SPIN_US), alternated twice
# 4. the 3K read, 256 answers: blocks of 64 / 256 (r4: the 256-token expert kernels ~40 % faster), default and
#    block switches, alternated twice
# 5. guessing: code / analysis / 3K, switches one group at a time (SAME AS the plain run, guess counts equal)
#    + all-empty rounds (OWN_SPEC_TAU=1.01) with CK1 (must equal the plain answers) + CK1 with OWN_HEAD_CQ /
#    OWN_SPEC_NGRAM=3 / prompt blocks 16 and 256 / OWN_ENG_LATE=0 OWN_ENG_EARLY=0 / OWN_TP_SPIN_US=300
# 6. card 2 kernel profiles (all-empty rounds with CK1, guessing with the best set) and a check timeline
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg90
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "build exit" $W/build-tp90.log 2>/dev/null; do sleep 10; done
grep -q "build exit 0" $W/build-tp90.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp90.log >> $sum
SP=
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
SK="OWN_SMALLK=1 OWN_SMALLK_DOTS=8" # tp90 default; given to tp89 for the comparison
XQ="OWN_XL2=15"                     # tp90: on its own queue
MS="OWN_MT_KVPAIR=1 OWN_MT_FIN_QB=1" # block switches that apply to every block
M7="OWN_MT_RIDE_MIN=7 OWN_MT_EU_MIN=7" # checks (<= 6 tokens) in the old small forms, prompt blocks unchanged
CK="OWN_CK1=1 OWN_RING_ONE=1 OWN_DR_NOWAIT=1"
WS="OWN_MT_WS=1"
tg=$(date '+%Y-%m-%d %H:%M:%S')
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h1|$T1" "h5|$T5" "h16|$TB OWN_PROMPT_BLOCK=16" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" \
         "h5ms|$T5 $MS" "h5m7|$T5 $MS $M7" "h5eu2|$T5 OWN_MT_EU_MIN=2" "h16ms|$TB OWN_PROMPT_BLOCK=16 $MS $M7" \
         "h64ms|$TB OWN_PROMPT_BLOCK=64 $MS" "h256ms|$TB OWN_PROMPT_BLOCK=256 $MS" "h1xq|$T1 $XQ" "h1nosk|$T1 OWN_SMALLK=0" \
         "h256eb|$TB OWN_PROMPT_BLOCK=256 OWN_MT_EU_BIG=0" "h5ws|$T5 $WS" "h5wsms|$T5 $WS $MS $M7" \
         "h16ws|$TB OWN_PROMPT_BLOCK=16 $WS" "h64ws|$TB OWN_PROMPT_BLOCK=64 $WS" "h256ws|$TB OWN_PROMPT_BLOCK=256 $WS" \
         "h256wsms|$TB OWN_PROMPT_BLOCK=256 $WS $MS"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg90 tp90 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $sum && { echo STOP_GATE1 >> $sum; exit 1; }
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|lookup guesses\|host io\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference
for k in "b64|OWN_PROMPT_BLOCK=64" "b256|OWN_PROMPT_BLOCK=256" "b64ms|OWN_PROMPT_BLOCK=64 $MS $M7" "b256ms|OWN_PROMPT_BLOCK=256 $MS" \
         "b64ws|OWN_PROMPT_BLOCK=64 $WS" "b256ws|OWN_PROMPT_BLOCK=256 $WS" "b256wsms|OWN_PROMPT_BLOCK=256 $WS $MS"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp90 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg90 tp90 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a89_$rd|89|$SK" "d90_$rd|90|" "xq_$rd|90|$XQ" "spin_$rd|90|OWN_TP_SPIN_US=300"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg90 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "d90|" "ms|$MS" "ws|$WS" "wsms|$WS $MS" "b256|OWN_PROMPT_BLOCK=256" "b256ws|OWN_PROMPT_BLOCK=256 $WS" \
           "b256wsms|OWN_PROMPT_BLOCK=256 $WS $MS"; do
    IFS='|' read -r nm extra <<< "$k"
    r p3k_${nm}_$rd tp90 $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $extra
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 5. guessing (prompt blocks of 64)
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DS"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
gk() { grep -o "[0-9]* of [0-9]* guesses kept" $1; }
sp() { local name=$1 n=$2; shift 2
  r $name tp90 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for n in code analysis; do
  sp ${n}_d90 $n $BEST
  sp ${n}_ck1 $n $BEST OWN_CK1=1
  sp ${n}_ck $n $BEST $CK
  sp ${n}_ckms $n $BEST $CK $MS
  sp ${n}_ckm7 $n $BEST $CK $MS $M7
  sp ${n}_ride7 $n $BEST $CK $MS OWN_MT_RIDE_MIN=7
  sp ${n}_eu7 $n $BEST $CK $MS OWN_MT_EU_MIN=7
  sp ${n}_ws $n $BEST $CK $MS $WS
  sp ${n}_wsm7 $n $BEST $CK $MS $M7 $WS
  a=$(gk $D/${n}_d90.log); t=$(gk $W/runs/tg89/${n}_d89.log); ok=1
  for v in ck1 ck ckms ckm7 ride7 eu7 ws wsm7; do [ "$(gk $D/${n}_$v.log)" = "$a" ] || ok=0; done
  [ -n "$a" ] && [ "$a" = "$t" ] && [ $ok = 1 ] && echo "${n} GUESSES_SAME ($a)" >> $sum || echo "${n} GUESSES_DIFFER ($a / tg89 $t)" >> $sum
done
# CK1 on the other paths (code prompt): the argmax readback on the copy queue, copied guesses, prompt blocks 16 / 256
sp code_ckhq code $BEST $CK OWN_HEAD_CQ=1
sp code_ckng code $BEST $CK OWN_SPEC_NGRAM=3
sp code_ckb16 code $BEST $CK OWN_PROMPT_BLOCK=16
sp code_ckb256 code $BEST $CK OWN_PROMPT_BLOCK=256
sp code_ckel code $BEST $CK OWN_ENG_LATE=0 OWN_ENG_EARLY=0
sp code_ckspin code $BEST $CK $MS OWN_TP_SPIN_US=300
# all-empty rounds: every round is a one-token check; must equal the plain answers (OWN_VERIFY_REF)
sp code_k0 code $PL $SPEC OWN_SPEC_TAU=1.01
sp code_k0ck code $PL $SPEC OWN_SPEC_TAU=1.01 $CK
for v in a d; do
  if [ $v = a ]; then envs=""; else envs="$CK $MS $WS"; fi
  r p3k_spec_${v} tp90 $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
a=$(gk $D/p3k_spec_a.log); b=$(gk $D/p3k_spec_d.log); t=$(gk $W/runs/tg89/p3k_spec_d89.log)
[ -n "$a" ] && [ "$a" = "$b" ] && [ "$a" = "$t" ] && echo "p3k GUESSES_SAME ($a)" >> $sum || echo "p3k GUESSES_DIFFER ($a / $b / tg89 $t)" >> $sum
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 28): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GUESSES_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. card 2 kernel profiles and a check timeline
r gprof_k0ck tp90 $PP/code-ids.txt 128 4096 1 $D/gprof_k0ck-ids.txt $PL $SPEC OWN_SPEC_TAU=1.01 $CK OWN_GPROF=2 OWN_GPROF_CARD=2
r gprof_ck tp90 $PP/code-ids.txt 256 4096 1 $D/gprof_ck-ids.txt $BEST $CK $MS $WS OWN_GPROF=2 OWN_GPROF_CARD=2
r tl_ck tp90 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $CK $MS $WS OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
