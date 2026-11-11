#!/bin/bash
# tg89: gate for tp89 = tp88 with OWN_ENG_CQ / OWN_PRE_K / OWN_ATT_M on by default (tg88) + routed-r2.patch (expert
# kernels with fewer instructions per weight, replaces the old forms; routed helper, bitwise in its benches) +
# opt-in: OWN_SMALLK=1 OWN_SMALLK_DOTS=8 (smallk-1.patch: one-work-group norms, compressor pool, engram gate, the
# stream mix's dots by proven brackets), OWN_XL2 (a cache prefetch of the next matrix on the second queue during
# each one-token exchange), OWN_PAIR_WG=96. SHORT six-card runs only (prompt 1, the 82 / 113-token prompts, the 3K
# document). A = tp88 with its tg88 options, for the speed comparison.
# 1. prompt-1 traces + 40 answers against runs/ab1; stop on any difference
# 2. 3K traces + 40 answers against gm64's tp84 blocks-of-16 trace; stop on any difference
# 3. prompt 1 speed, 128 answers: A / tp89 default / +SMALLK / +XL2 / +PAIR_WG=96 / all, alternated twice
# 4. the 3K read (blocks of 64; tg88: 256 is slower), 256 answers: A / tp89 / tp89 + the block attention forms at 64
#    (OWN_ATT_M_MAX=64; tp89 uses them up to 16 tokens) / tp89 all, alternated twice
# 5. guessing: code / analysis / 3K with tp89 default and all (SAME AS the plain run; the guess counts must equal
#    tg88's: the draft's values do not change)
# 6. card 2 kernel profile (one-token, all) and timelines (one-token steps, checks) with all
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg89
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "build exit" $W/build-tp89.log 2>/dev/null; do sleep 10; done
grep -q "build exit 0" $W/build-tp89.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp89.log >> $sum
SP=
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "own_run_v41_" > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
FB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_EU=6 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1 OWN_MT_W16=0"
A88="OWN_ENG_CQ=1 OWN_PRE_K=1 OWN_ATT_M=1" # tp88's tg88 options (tp89 defaults)
SK="OWN_SMALLK=1 OWN_SMALLK_DOTS=8"
XL="OWN_XL2=15"
PW="OWN_PAIR_WG=96"
ALL="$SK $XL $PW"
tg=$(date '+%Y-%m-%d %H:%M:%S')
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h16|$TB OWN_PROMPT_BLOCK=16" "h5|$T5" "h1|$T1" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" \
         "h1sk|$T1 $SK" "h16sk|$TB OWN_PROMPT_BLOCK=16 $SK" "h5sk|$T5 $SK" "h64sk|$TB OWN_PROMPT_BLOCK=64 $SK" \
         "h1sk4|$T1 OWN_SMALLK=1 OWN_SMALLK_DOTS=4" "h1xl|$T1 $XL" "h1pw|$T1 $PW" "h16pw|$TB OWN_PROMPT_BLOCK=16 $PW" \
         "h5all|$T5 $ALL" "h1all|$T1 $ALL" "h256fb|$FB OWN_PROMPT_BLOCK=256"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg89 tp89 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $sum && { echo STOP_GATE1 >> $sum; exit 1; }
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|lookup guesses\|host io\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference
for k in "b256|OWN_PROMPT_BLOCK=256" "b64|OWN_PROMPT_BLOCK=64" "b16|OWN_PROMPT_BLOCK=16" "b256sk|OWN_PROMPT_BLOCK=256 $SK" \
         "b256pw|OWN_PROMPT_BLOCK=256 $PW" "b64all|OWN_PROMPT_BLOCK=64 $ALL"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp89 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg89 tp89 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a88_$rd|88|$A88" "d89_$rd|89|" "sk_$rd|89|$SK" "xl_$rd|89|$XL" "pw_$rd|89|$PW" "all_$rd|89|$ALL"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg89 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "a88|88|$A88" "d89|89|" "am64|89|OWN_ATT_M_MAX=64" "all|89|$ALL"; do
    IFS='|' read -r nm b extra <<< "$k"
    r p3k_${nm}_$rd tp$b $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $extra
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 5. guessing (blocks of 256)
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
gk() { grep -o "[0-9]* of [0-9]* guesses kept" $1; }
for n in code analysis; do
  for k in "a88|88|$A88" "d89|89|" "all|89|$ALL"; do
    IFS='|' read -r v b envs <<< "$k"
    r ${n}_$v tp$b $PP/$n-ids.txt 512 4096 1 $D/${n}_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/${n}_$v-spec.txt \
      OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
  done
  a=$(gk $D/${n}_a88.log); b=$(gk $D/${n}_d89.log); c=$(gk $D/${n}_all.log); t=$(gk $W/runs/tg88/${n}_q256.log)
  [ -n "$a" ] && [ "$a" = "$b" ] && [ "$a" = "$c" ] && [ "$a" = "$t" ] && echo "${n} GUESSES_SAME ($a)" >> $sum || echo "${n} GUESSES_DIFFER ($a / $b / $c / tg88 $t)" >> $sum
done
for k in "a88|88|$A88" "d89|89|" "all|89|$ALL"; do
  IFS='|' read -r v b envs <<< "$k"
  r p3k_spec_$v tp$b $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
done
a=$(gk $D/p3k_spec_a88.log); b=$(gk $D/p3k_spec_d89.log); c=$(gk $D/p3k_spec_all.log)
[ -n "$a" ] && [ "$a" = "$b" ] && [ "$a" = "$c" ] && echo "p3k GUESSES_SAME ($a)" >> $sum || echo "p3k GUESSES_DIFFER ($a / $b / $c)" >> $sum
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 9): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GUESSES_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. card 2 kernel profile (one-token, all) and timelines with all
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
r gprof_all tp89 $P1 48 4096 -1 $D/gprof_all-ids.txt $PL $ALL OWN_GPROF=2 OWN_GPROF_CARD=2
r tl_one tp89 $P1 40 4096 -1 $D/tl_one-ids.txt $PL $ALL OWN_TIMELINE=$D/tl_one.txt OWN_TIMELINE_STEPS=20-27
r tl_ck tp89 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $ALL OWN_DSPARK=$DS OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
