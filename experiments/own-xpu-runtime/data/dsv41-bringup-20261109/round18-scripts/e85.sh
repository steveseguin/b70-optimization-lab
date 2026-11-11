#!/bin/bash
# OWN_IDX_CAND (tp71 = tp70 + the same for blocks: prompt reading and guess checks score and select only each
# token's layer-20 candidate rows past 16,384 rows; IndexerScoreBCM + TopKSelMC). Waits for e84 (exits if it
# stopped). Builds tp71 from the src71 snapshot, then: (1) gates of the default (option off); (2) OWN_IDX_CAND=2
# on the 34K document (every one-token list and one block layer in 37 compared with the full score + select);
# (3) OWN_IDX_CAND=1: the 34K / 69K / 95K reads + 256 plain answer tokens (must equal e82's), guessing on 34K /
# 69K (SAME as the plain run). Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e84/summary.txt 2>/dev/null; do sleep 10; done
grep -q STOP $S/runs/e84/summary.txt && exit 1
while systemctl --user is-active --quiet dsv41-e84; do sleep 2; done
D=$S/runs/e85
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
cd $S/src71 # snapshot of engine/src + planning/dsv41-fixtures taken when this script was written
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $S/own_run_v41_tp71 -lze_loader > $S/build-tp71.log 2>&1
r1=$?
echo "tp71 build exit $r1 in $(( $(date +%s) - t0 )) s" >> $sum
[ $r1 -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
T16="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G OWN_MT_TGR=16:4,1:4 OWN_MT_TGR_ROWS=0"
T5="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=5 OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3 $G"
T1="OWN_TP=6 OWN_TP_THREADS=1 OWN_PROMPT_BLOCK=1 $G"
tg=$(date '+%Y-%m-%d %H:%M:%S')
$S/run_exp.sh e85 tp71 "h16|$T16|trace" "h5|$T5|trace" "h1|$T1|trace" "p1|$PL|speed"
sed -i '/^DONE$/d' $sum
journalctl -k --since "$tg" -o cat | grep -iE "$J" | head -3 | sed 's/^/FAULT: /' >> $sum
grep -q "TRACE_DIFFERS\|IDS40_DIFFER\|SPEED128_DIFFER\|exit [^0]\|FAULT" $sum && { echo STOP_GATE >> $sum; exit 1; }
bin=$S/own_run_v41_tp71
X=$S/prompts/xl
r() { local name=$1 pr=$2 nt=$3 ms=$4; shift 4; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "free after load\|prompt:\|decode:\|spec decode\|host io\|rror\|timed out\|exceeds\|idx_cand check" $D/$name.log | tail -n 12 | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
same() { cmp -s <(head -$3 $D/$1-ids.txt) <(head -$3 $2) && echo "$1 ANSWER$3_SAME" >> $sum || echo "$1 ANSWER$3_DIFFERS" >> $sum; }
ms() { echo $(( ( $(wc -l < $1) + 256 + 1023 ) / 1024 * 1024 )); }
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
p=$X/x34k-ids.txt; r x34k_check $p 64 $(ms $p) $PL OWN_IDX_CAND=2; same x34k_check $S/runs/e82/x34k_plain-ids.txt 64
grep -q "idx_cand check.*MISMATCH" $D/x34k_check.log && { echo STOP_CHECK_MISMATCH >> $sum; exit 1; }
grep -q "idx_cand check: [0-9]* lists, 0 mismatches.*block" $D/x34k_check.log || { echo STOP_CHECK_NOT_RUN >> $sum; exit 1; }
grep "idx_cand check:" $D/x34k_check.log | tail -2 | sed 's/^/x34k_check: /' >> $sum
for n in x34k x69k x95k; do
  p=$X/$n-ids.txt; r ${n}_cand $p 256 $(ms $p) $PL OWN_IDX_CAND=1; same ${n}_cand $S/runs/e82/${n}_plain-ids.txt 256
done
for n in x34k x69k; do
  p=$X/$n-ids.txt; r ${n}_cspec $p 256 $(ms $p) $BEST OWN_IDX_CAND=1 OWN_VERIFY_REF=$S/runs/e82/${n}_plain-ids.txt OWN_DSPARK=$DS
done
echo ALLDONE >> $sum
