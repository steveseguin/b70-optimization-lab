#!/bin/bash
# tg87: gate for tp87 = tp86 (repo) with: OWN_XPF removed (closed in tg86b), the attention defaults flipped
# (OWN_ATT_HG=1 OWN_ATT_PK=1 now default; tg86 + tg86c: traces identical, 3K + guessing SAME), OWN_XPULL_GRF=128
# (XchgPull built for 128 registers: no register-mode change around each of the 83 pull exchanges per step), the
# mtx64 patch (prompt blocks up to 64 tokens, gm64: identical), the draft router fix (dr-route128.patch: the draft
# picks from its own 128 experts, not 384 with leftovers) and OWN_TIMELINE_CHECKS. SHORT six-card runs only.
# 1. traces + 40 answers: defaults (blocks 16 / 5 / 1 / 64), XPULL_GRF=128 on blocks 1 / 16 / 64
# 2. prompt 1, 128 answers: default / XPULL_GRF=128 alternated twice
# 3. the 3K document, 256 answers: blocks 16 default / blocks 64 + XPULL_GRF=128, alternated twice
# 4. guessing (code / analysis / 3K) at blocks 16 and 64 with XPULL_GRF=128: SAME AS the plain run, and the guess /
#    kept counts must match between 16 and 64 (the router fix)
# 5. timelines: one-token steps (OWN_TIMELINE 20-27) and guessing checks on the code prompt (OWN_TIMELINE_CHECKS)
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
D=$W/runs/tg87
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
# a window with only corrected PCIe records (the firmware's "{N}[Hardware Error]" lines, severity corrected) is
# noted and the run goes on (as g83); fatal / recoverable records or any other fault line stop it
fcheck() { local w f; w=$(journalctl -k --since "$1" -o cat); f=$(echo "$w" | grep -iE "$J"); [ -z "$f" ] && return 0
  if ! echo "$f" | grep -qvE '^\{[0-9]+\}\[Hardware Error\]' && ! echo "$w" | grep -qE 'event severity: (fatal|recoverable)'; then
    echo "WARN corrected PCIe: $(echo "$w" | grep -E 'device_id: 0000' | sort | uniq -c | tr -s ' ' | tr '\n' ';')" >> $sum; return 0; fi
  echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
until grep -q "build exit" $W/build-tp87.log 2>/dev/null; do sleep 10; done
grep -q "build exit 0" $W/build-tp87.log || { echo STOP_BUILD >> $sum; exit 1; }
tail -1 $W/build-tp87.log >> $sum
# card sharing: helpers run one-card benches only while $W/six.active is absent, each holding a file in $W/locks;
# this gate marks itself active, then waits for the helpers' running benches to end
touch $W/six.active
until [ -z "$(ls -A $W/locks 2>/dev/null)" ]; do sleep 5; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null; rm -f $W/six.active' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T64="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=64 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
XG="OWN_XPULL_GRF=128"
tg=$(date '+%Y-%m-%d %H:%M:%S')
# ---- 1. traces (trace mode parks the card threads: never the PL settings here)
for k in "h16|$T16" "h5|$T5" "h1|$T1" "h64|$T64" "h1xg|$T1 $XG" "h16xg|$T16 $XG" "h64xg|$T64 $XG" \
         "h1att0|$T1 OWN_ATT_HG=4 OWN_ATT_PK=0"; do
  IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg87 tp87 "$name|$envs|trace"; sed -i '/^DONE$/d' $sum
done
fcheck "$tg"
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|exit [^0]" $sum && { echo STOP_GATE >> $sum; exit 1; }
# ---- 2. prompt 1 speed, 128 answers (SPEED128 against runs/ab1)
for rd in 1 2; do
  for k in "s_def$rd|" "s_xg$rd|$XG"; do
    IFS='|' read -r name envs <<< "$k"; $W/run_exp.sh tg87 tp87 "$name|$PL $envs|speed"; sed -i '/^DONE$/d' $sum
  done
  fcheck "$tg"
done
grep -q "SPEED128_DIFFER\|exit [^0]" $sum && { echo STOP_SPEED >> $sum; exit 1; }
r() { local name=$1 b=$2 pr=$3 nt=$4 mx=$5 eos=$6 out=$7; shift 7; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_$b - $nt $out $mx > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|host io\|rror\|timed out\|exceeds\|MISMATCH" $D/$name.log | sed "s/^/$name: /" >> $sum
  grep -h "check:" $D/$name.log | tail -2 | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
same() { cmp -s <(head -$3 $1) <(head -$3 $2) && echo "$4 ANSWER$3_SAME" >> $sum || echo "$4 ANSWER$3_DIFFERS" >> $sum; }
# ---- 3. the 3K document
p=$W/prompts/p3k-ids.txt
for k in "d1|" "n1|OWN_PROMPT_BLOCK=64 $XG" "d2|" "n2|OWN_PROMPT_BLOCK=64 $XG"; do
  IFS='|' read -r nm envs <<< "$k"; r p3k_$nm tp87 $p 256 4096 -1 $D/p3k_$nm-ids.txt $PL $envs
  same $D/p3k_$nm-ids.txt $W/runs/e52/p3kplain-ids.txt 256 p3k_$nm
done
# ---- 4. guessing, blocks 16 and 64
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
for n in code analysis; do
  for bk in 16 64; do
    r ${n}_q$bk tp87 $PP/$n-ids.txt 512 4096 1 $D/${n}_q$bk-ids.txt $BEST OWN_PROMPT_BLOCK=$bk $XG \
      OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS
  done
done
for bk in 16 64; do
  r p3k_spec$bk tp87 $p 256 4096 -1 $D/p3k_spec$bk-ids.txt $BEST OWN_PROMPT_BLOCK=$bk $XG \
    OWN_VERIFY_REF=$W/runs/e52/p3kplain-ids.txt OWN_DSPARK=$DS
done
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count (of 6): /' >> $sum
for n in code analysis p3k; do
  a=$(grep -h "spec decode" $D/${n}_q16.log $D/${n}_spec16.log 2>/dev/null | head -1 | grep -oE "[0-9]+ cycles|[0-9]+ of [0-9]+ guesses" | head -2 | tr '\n' ' ')
  b=$(grep -h "spec decode" $D/${n}_q64.log $D/${n}_spec64.log 2>/dev/null | head -1 | grep -oE "[0-9]+ cycles|[0-9]+ of [0-9]+ guesses" | head -2 | tr '\n' ' ')
  [ "$a" = "$b" ] && echo "$n GUESS16_64_SAME ($a)" >> $sum || echo "$n GUESS16_64_DIFFER (16: $a / 64: $b)" >> $sum
done
grep -q "ANSWER.*DIFFERS\|DIFFERS from" $sum && echo "SOME_DIFFER" >> $sum
# ---- 5. timelines (device clock; one-token steps 20-27, then the guessing checks 20-27 on the code prompt)
r tl_one tp87 $L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt 40 4096 -1 $D/tl_one-ids.txt \
  $PL $XG OWN_TIMELINE=$D/tl_one.txt OWN_TIMELINE_STEPS=20-27
r tl_ck tp87 $PP/code-ids.txt 256 4096 1 $D/tl_ck-ids.txt $BEST $XG OWN_DSPARK=$DS OWN_TIMELINE=$D/tl_ck.txt OWN_TIMELINE_CHECKS=20-27
echo ALLDONE >> $sum
