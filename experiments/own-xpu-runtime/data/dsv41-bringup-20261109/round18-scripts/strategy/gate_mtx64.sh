#!/bin/bash
# gm64: gate for prompt blocks of up to 64 tokens (OWN41_MTX=64; mtx64.patch on top of tp84's sources).
# SHORT six-card runs only (prompt 1 = 36 tokens, the 82 / 113-token guessing prompts, the 3K document).
# 1. traces + 40 answers on prompt 1 against runs/ab1 (blocks of 64 = one block of 36, 33 + 3, 32 + 4, 16, 5, 1, and the
#    fallback forms past 16 tokens); stop on any difference
# 2. traces + 40 answers on the 3K document: tp84 blocks of 16 (reference) vs mtx64 blocks of 64 / 37 / 32 / 16
# 3. the 3K read at 16 / 32 / 64 alternated twice (+ tp84 at 16), 256 answers against runs/e52's plain run
# 4. guessing (code / analysis prompts) with prompt blocks of 16 and 64: SAME AS the plain run, same guess counts
# 5. free card memory after load, tp84 vs mtx64
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/gm64
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
# a window with only corrected PCIe records (the firmware's "{N}[Hardware Error]" lines, severity corrected: card
# 0000:23's link has logged corrected receiver errors since the 19:43 reset) is noted and the run goes on (as g83)
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
[ -x $W/mtx64/own_run_v41_mtx64 ] || { echo STOP_BUILD >> $sum; exit 1; }
ln -sf $W/mtx64/own_run_v41_mtx64 $W/own_run_v41_mtx64 # run_exp.sh runs $W/own_run_v41_<bin>
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
TB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
# fallback forms past 16 tokens: no token groups, no W16 forms, no unpacked-row groups (DenseRowsG<D, D::MTG>,
# GemvTMG<16>), slot-major experts (384 slots), the per-token small launches (HcDotsRowsM per 16 tokens)
FB="OWN_TP=6 OWN_TP_THREADS=1 OWN_MT_EU=6 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1 OWN_MT_W16=0"
tg=$(date '+%Y-%m-%d %H:%M:%S')
# ---- 1. prompt 1 traces (stop on any difference)
for k in "h64|$TB OWN_PROMPT_BLOCK=64" "h33|$TB OWN_PROMPT_BLOCK=33" "h32|$TB OWN_PROMPT_BLOCK=32" \
         "h16|$TB OWN_PROMPT_BLOCK=16" "h5|$T5" "h1|$T1" \
         "h64fb|$FB OWN_PROMPT_BLOCK=64" "h16fb|$FB OWN_PROMPT_BLOCK=16" "h64eu0|$TB OWN_PROMPT_BLOCK=64 OWN_MT_EU=0"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh gm64 mtx64 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $sum && { echo STOP_GATE1 >> $sum; exit 1; }
# (not a stop: the OWN_MT_SMALL=0 forms are not the default; a difference here is reported)
$W/run_exp.sh gm64 mtx64 "h64s0|$FB OWN_PROMPT_BLOCK=64 OWN_MT_SMALL=0 OWN_MT_RFUSE=0|trace"; sed -i '/^DONE$/d' $sum
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  grep -h "GiB free" $D/$name.log | tr '\n' ' ' | sed "s/^/$name: /; s/$/\n/" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
p=$W/prompts/p3k-ids.txt
# ---- 2. 3K traces: tp84 blocks of 16 is the reference
r t3k_ref tp84 $p 40 4096 1 $D/t3k_ref-ids.txt $TB OWN_PROMPT_BLOCK=16 OWN_TRACE=$D/t3k_ref.trc OWN_TRACE_STEPS=3
for m in 64 37 32 16; do
  r t3k_b$m mtx64 $p 40 4096 1 $D/t3k_b$m-ids.txt $TB OWN_PROMPT_BLOCK=$m OWN_TRACE=$D/t3k_b$m.trc OWN_TRACE_STEPS=3
  cmp -s $D/t3k_b$m.trc $D/t3k_ref.trc && echo "t3k_b$m TRACE_IDENTICAL" >> $sum || echo "t3k_b$m TRACE_DIFFERS" >> $sum
  cmp -s $D/t3k_b$m-ids.txt $D/t3k_ref-ids.txt && echo "t3k_b$m IDS40_SAME" >> $sum || echo "t3k_b$m IDS40_DIFFER" >> $sum
done
grep -q "TRACE_DIFFERS\|IDS40_DIFFER" $sum && { echo STOP_GATE2 >> $sum; exit 1; }
# ---- 3. 3K read speed (blocks of 16 / 32 / 64 alternated twice, tp84 at 16 once per round); 256 answers
for rd in 1 2; do
  for k in "b16|mtx64|16" "b32|mtx64|32" "b64|mtx64|64" "old16|tp84|16"; do
    IFS='|' read -r nm bn m <<< "$k"
    r p3k_${nm}_$rd $bn $p 256 4096 -1 $D/p3k_${nm}_$rd-ids.txt $PL OWN_PROMPT_BLOCK=$m
    same $D/p3k_${nm}_$rd-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_${nm}_$rd
  done
done
# ---- 4. guessing with prompt blocks of 16 and 64 (the draft's rows are injected per prompt block)
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
for n in code analysis; do
  for m in 16 64; do
    r ${n}_q$m mtx64 $PP/$n-ids.txt 512 4096 1 $D/${n}_q$m-ids.txt $BEST OWN_PROMPT_BLOCK=$m \
      OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
  done
  # the draft's rows do not depend on the prompt block size: the same guesses, the same kept counts
  a=$(grep -o "[0-9]* of [0-9]* guesses kept" $D/${n}_q16.log); b=$(grep -o "[0-9]* of [0-9]* guesses kept" $D/${n}_q64.log)
  [ -n "$a" ] && [ "$a" = "$b" ] && echo "${n} GUESSES_SAME ($a)" >> $sum || echo "${n} GUESSES_DIFFER ($a / $b)" >> $sum
done
r p3k_spec64 mtx64 $p 256 4096 -1 $D/p3k_spec64-ids.txt $BEST OWN_PROMPT_BLOCK=64 OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 5): /' >> $sum
grep -q "ANSWER.*DIFFERS\|DIFFERS from\|GUESSES_DIFFER" $sum && echo "SOME_DIFFER" >> $sum
echo ALLDONE >> $sum
