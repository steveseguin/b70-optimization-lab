#!/bin/bash
# tg91: gate for tp91 = tp90 with the tg90 winners on by default (OWN_MT_WS, OWN_CK1, OWN_RING_ONE, OWN_DR_NOWAIT,
# OWN_MT_KVPAIR + OWN_MT_FIN_QB for blocks of <= OWN_MT_MS_MAX=16) + draft-head-1 (opt-in: OWN_DR_VOCAB, OWN_DR_WS,
# OWN_DR_ANCHOR_ARG, OWN_DR_TGW; the draft only proposes) + pcd-1 (opt-in: OWN_MT_DSPLIT = prompt item C, the stream
# mixes' dot rows split across the cards by token; OWN_MT_SKDOTS = the one-token path's fast dot rows in blocks).
# SHORT six-card runs only (prompt 1, the guessing prompts, the 3K document).
# 0. pcd-1's six-card exchange test (2,000 iterations, PASS required) and its one-card bench (card 1, bitwise lines)
# 1. prompt-1 traces + 40 answers against runs/ab1 (tp91 defaults at 1 / 5 / 16 / 64 / 256; OWN_MT_WS=0; the pcd
#    switches at several block sizes, finish forms, RIDE=0, uneven shares)
# 2. 3K traces + 40 answers against gm64's tp84 trace
# 3. prompt 1 speed, 128 answers: tp90 (with the new defaults as switches) / tp91, alternated twice
# 4. the 3K read, 256 answers: tp91 / DSPLIT / SKDOTS / both at 64; both at 256; alternated twice
# 5. guessing: tp91 default (guess logs must equal tg90's code_ws / analysis_ws run), each draft switch (logs equal
#    except OWN_DR_VOCAB), the vocabulary list (answers SAME, kept within ~1 %), TAU 0.34 / 0.40, the pcd switches
#    in checks (MIN=2); prose + 3K; prompt blocks 16 / 256 with the vocabulary list
# 6. card 2 kernel profile and a check timeline with the best set
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg91
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "tp91 build exit" $W/build-tp91.log 2>/dev/null; do sleep 10; done
grep -q "tp91 build exit 0" $W/build-tp91.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -3 $W/build-tp91.log >> $sum
SP=
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
tg=$(date '+%Y-%m-%d %H:%M:%S')
# ---- 0. pcd-1's tests
if [ -x $W/pcd/xchg_pull2_test ]; then
  NEOReadDebugKeys=1 DisableIndirectAccess=1 timeout 540 $W/pcd/xchg_pull2_test 2000 > $D/xtest.log 2>&1
  echo "xtest exit $?" >> $sum; grep -E "wrong|time:|PASS|FAIL" $D/xtest.log | sed 's/^/xtest: /' >> $sum
  fcheck "$tg"
  grep -q "PASS" $D/xtest.log && ! grep -q "FAIL" $D/xtest.log || { echo STOP_XTEST >> $sum; exit 1; }
else echo "xtest NOT BUILT" >> $sum; echo STOP_XTEST >> $sum; exit 1; fi
if [ -x $W/pcd/bench_dsplit ]; then
  ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 180 $W/pcd/bench_dsplit > $D/bench_dsplit.log 2>&1
  echo "bench_dsplit exit $?" >> $sum; grep -iE "pass|fail|differ|wrong|identical" $D/bench_dsplit.log | head -40 | sed 's/^/bench: /' >> $sum
  fcheck "$tg"
  grep -qiE "fail|differ" $D/bench_dsplit.log && { echo STOP_BENCH >> $sum; exit 1; }
fi
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
N90="OWN_MT_WS=1 OWN_CK1=1 OWN_RING_ONE=1 OWN_DR_NOWAIT=1 OWN_MT_KVPAIR=1 OWN_MT_FIN_QB=1" # tp90 + tg90's winners
DS="OWN_MT_DSPLIT=1"
SK="OWN_MT_SKDOTS=8"
DS2="OWN_MT_DSPLIT=1 OWN_MT_DSPLIT_MIN=2"
SK2="OWN_MT_SKDOTS=8 OWN_MT_SKDOTS_MIN=2"
UNEV="OWN_MT_DSPLIT_WA=0,0,0,0,1,1 OWN_MT_DSPLIT_WF=1,0,0,0,0,1"
# ---- 1. prompt-1 traces (trace mode parks the card threads: never the PL settings here)
for k in "h1|$T1" "h5|$T5" "h16|$TB OWN_PROMPT_BLOCK=16" "h64|$TB OWN_PROMPT_BLOCK=64" "h256|$TB OWN_PROMPT_BLOCK=256" \
         "h64ws0|$TB OWN_PROMPT_BLOCK=64 OWN_MT_WS=0" "h5ms0|$T5 OWN_MT_KVPAIR=0 OWN_MT_FIN_QB=0" \
         "h16ds|$TB OWN_PROMPT_BLOCK=16 $DS" "h64ds|$TB OWN_PROMPT_BLOCK=64 $DS" "h256ds|$TB OWN_PROMPT_BLOCK=256 $DS" \
         "h5ds2|$T5 $DS2" "h64fin0|$TB OWN_PROMPT_BLOCK=64 $DS OWN_MT_DSPLIT_FIN=0" \
         "h64fin1|$TB OWN_PROMPT_BLOCK=64 $DS OWN_MT_DSPLIT_FIN=1" "h64ride0|$TB OWN_PROMPT_BLOCK=64 $DS OWN_MT_RIDE=0" \
         "h64unev|$TB OWN_PROMPT_BLOCK=64 $DS $UNEV" "h5unev|$T5 $DS2 $UNEV" \
         "h64sk|$TB OWN_PROMPT_BLOCK=64 $SK" "h256sk|$TB OWN_PROMPT_BLOCK=256 $SK" "h5sk2|$T5 $SK2" \
         "h64sk4|$TB OWN_PROMPT_BLOCK=64 OWN_MT_SKDOTS=4" "h64dssk|$TB OWN_PROMPT_BLOCK=64 $DS $SK" \
         "h256dssk|$TB OWN_PROMPT_BLOCK=256 $DS $SK" "h5dssk2|$T5 $DS2 $SK2"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg91 tp91 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $sum && { echo STOP_GATE1 >> $sum; exit 1; }
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|kept guesses\|lookup guesses\|host io\|rows per card\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
REF=$W/runs/gm64/t3k_ref # tp84, blocks of 16 (gm64)
# ---- 2. 3K traces against the tp84 reference
for k in "b64|OWN_PROMPT_BLOCK=64" "b256|OWN_PROMPT_BLOCK=256" "b64ds|OWN_PROMPT_BLOCK=64 $DS" "b64sk|OWN_PROMPT_BLOCK=64 $SK" \
         "b64dssk|OWN_PROMPT_BLOCK=64 $DS $SK" "b256dssk|OWN_PROMPT_BLOCK=256 $DS $SK"; do
  IFS='|' read -r nm envs <<< "$k"
  r t3k_$nm tp91 $p 40 4096 1 $D/t3k_$nm-ids.txt $TB $envs OWN_TRACE=$D/t3k_$nm.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_$nm.trc $REF.trc && echo "t3k_$nm TRACE_IDENTICAL" >> $sum || echo "t3k_$nm TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_$nm-ids.txt $REF-ids.txt && echo "t3k_$nm IDS40_SAME" >> $sum || echo "t3k_$nm IDS40_DIFFER" >> $sum
  rm -f $D/t3k_$nm.trc # 70 MB each; the comparison is recorded
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. prompt 1 speed, 128 answers (SPEED128 against runs/ab1); a warm-up run first (disk reads of engram rows)
$W/run_exp.sh tg91 tp91 "warm|$PL|speed"; sed -i '/^DONE$/d' $sum
for rd in 1 2; do
  for k in "a90_$rd|90|$N90" "d91_$rd|91|"; do
    IFS='|' read -r name b envs <<< "$k"; $W/run_exp.sh tg91 tp$b "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
# ---- 4. the 3K read speed, 256 answers (alternated twice)
for rd in 1 2; do
  for k in "d91|" "ds|$DS" "sk|$SK" "dssk|$DS $SK" "b256dssk|OWN_PROMPT_BLOCK=256 $DS $SK"; do
    IFS='|' read -r nm extra <<< "$k"
    r p3k_${nm}_$rd tp91 $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL $extra
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 5. guessing (prompt blocks of 64)
DSP=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
SPEC="OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096 OWN_DSPARK=$DSP"
BEST="$PL $SPEC OWN_SPEC_TAU=0.5"
VALL=$D/vocab-all.txt; seq 0 129279 > $VALL
VOC="OWN_DR_VOCAB=$W/draft/vocab/cand-c32k-dict.txt OWN_DR_VOCAB_N=60000"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
gk() { grep -o "[0-9]* of [0-9]* guesses kept" $1; }
# guess logs: columns 1-7 (5 confidences, guesses, kept) or 6-7 (guesses, kept) equal
glog() { local a=$1 b=$2 cols=$3 tag=$4
  if [ "$cols" = all ]; then cmp -s <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $a) <(awk '{print $1,$2,$3,$4,$5,$6,$7}' $b)
  else cmp -s <(awk '{print $6,$7}' $a) <(awk '{print $6,$7}' $b); fi && echo "$tag GLOG_SAME ($cols)" >> $sum || echo "$tag GLOG_DIFFER ($cols)" >> $sum; }
sp() { local name=$1 n=$2; shift 2
  r $name tp91 $PP/$n-ids.txt 512 4096 1 $D/$name-ids.txt "$@" OWN_SPEC_LOG=$D/$name-spec.txt \
    OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt; }
for n in code analysis; do
  sp ${n}_d91 $n $BEST
  glog $D/${n}_d91-spec.txt $W/runs/tg90/${n}_ws-spec.txt all ${n}_d91_vs_tg90ws
  sp ${n}_drws $n $BEST OWN_DR_WS=1;            glog $D/${n}_drws-spec.txt $D/${n}_d91-spec.txt all ${n}_drws
  sp ${n}_dranc $n $BEST OWN_DR_ANCHOR_ARG=1;   glog $D/${n}_dranc-spec.txt $D/${n}_d91-spec.txt all ${n}_dranc
  sp ${n}_drtgw5 $n $BEST OWN_DR_TGW=5;         glog $D/${n}_drtgw5-spec.txt $D/${n}_d91-spec.txt all ${n}_drtgw5
  sp ${n}_vall $n $BEST OWN_DR_VOCAB=$VALL OWN_DR_VOCAB_N=129280; glog $D/${n}_vall-spec.txt $D/${n}_d91-spec.txt kk ${n}_vall
  sp ${n}_voc $n $BEST $VOC
  sp ${n}_vocall $n $BEST $VOC OWN_DR_WS=1 OWN_DR_ANCHOR_ARG=1
  sp ${n}_tau34 $n $PL $SPEC OWN_SPEC_TAU=0.34
  sp ${n}_tau40 $n $PL $SPEC OWN_SPEC_TAU=0.40
  sp ${n}_dssk2 $n $BEST $DS2 $SK2;             glog $D/${n}_dssk2-spec.txt $D/${n}_d91-spec.txt all ${n}_dssk2
done
for n in prose; do
  sp ${n}_d91 $n $BEST
  sp ${n}_voc $n $BEST $VOC
done
sp code_vocb16 code $BEST $VOC OWN_PROMPT_BLOCK=16
sp code_vocb256 code $BEST $VOC OWN_PROMPT_BLOCK=256
for v in d91 voc; do
  if [ $v = d91 ]; then envs=""; else envs="$VOC OWN_DR_WS=1 OWN_DR_ANCHOR_ARG=1"; fi
  r p3k_spec_$v tp91 $p 256 4096 -1 $D/p3k_spec_$v-ids.txt $BEST $envs OWN_SPEC_LOG=$D/p3k_spec_$v-spec.txt \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 26): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|DIFFERENT FROM\|GLOG_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
# ---- 6. card 2 kernel profile and a check timeline (default + the draft's bit-identical switches)
r gprof_ck tp91 $PP/code-ids.txt 256 4096 1 $D/gprof_ck-ids.txt $BEST OWN_DR_WS=1 OWN_DR_ANCHOR_ARG=1 OWN_GPROF=2 OWN_GPROF_CARD=2 OWN_GPROF_DECODE=1
r tl_ck tp91 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST OWN_DR_WS=1 OWN_DR_ANCHOR_ARG=1 OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
