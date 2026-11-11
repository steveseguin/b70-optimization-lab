#!/bin/bash
# What makes plain answers slower on long documents (82 tokens 78 tok/s -> 69K 60 tok/s, e82). Waits for e82
# (exits if it stopped), builds tp69 (= tp68 + OWN_GPROF_DECODE=1: the profile counts answer steps only, a
# runner print change, no kernel change), then: (0) plain 128-token answer after prompt 1 (must equal ab1) and
# 256 tokens after the 3K document (must equal e52's) as speed points; (1) kernel-time profiles (OWN_GPROF=2,
# answer steps only, not speed measurements) of card 2 after prompt 1 / 3K / 19K / 69K and of card 0 after 69K,
# 64 answer tokens each (must equal the plain answers). Stops at the first fault line.
set -u
S=/tmp/claude-1000/-home-steve/6f61a0f6-fd06-49a3-b5b4-babc9645cc37/scratchpad
until grep -q "ALLDONE\|STOP" $S/runs/e82/summary.txt 2>/dev/null; do sleep 10; done
grep -q STOP $S/runs/e82/summary.txt && exit 1
while systemctl --user is-active --quiet dsv41-e82; do sleep 2; done
D=$S/runs/e83
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
cd $S/src69 # snapshot of engine/src + planning/dsv41-fixtures taken when this script was written
t0=$(date +%s)
PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I planning/dsv41-fixtures -I src planning/dsv41-fixtures/own_run_v41.cpp -o $S/own_run_v41_tp69 -lze_loader > $S/build-tp69.log 2>&1
rc=$?
echo "tp69 build exit $rc in $(( $(date +%s) - t0 )) s" >> $sum
[ $rc -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
python3 -I $S/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
bin=$S/own_run_v41_tp69
X=$S/prompts/xl
P1=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
r() { local name=$1 pr=$2 nt=$3 ms=$4; shift 4; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=-1 $bin - $nt $D/$name-ids.txt $ms > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "free after load\|prompt:\|decode:\|host io\|rror\|timed out\|exceeds\|  total \|kernels .* ms, launches" $D/$name.log | sed "s/^/$name: /" >> $sum
  local f; f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  if [ -n "$f" ] || [ $rc -ne 0 ]; then echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; fi; }
same() { cmp -s <(head -$3 $D/$1-ids.txt) <(head -$3 $2) && echo "$1 ANSWER$3_SAME" >> $sum || echo "$1 ANSWER$3_DIFFERS" >> $sum; }
ms() { echo $(( ( $(wc -l < $1) + 256 + 1023 ) / 1024 * 1024 )); }
r p1_plain $P1 128 $(ms $P1) $PL; same p1_plain $S/runs/ab1/base-speed-ids.txt 128
p=$S/prompts/p3k-ids.txt; r p3k_plain $p 256 $(ms $p) $PL; same p3k_plain $S/runs/e52/p3kplain-ids.txt 256
PR="OWN_GPROF=2 OWN_GPROF_DECODE=1"
r p1_prof2 $P1 64 $(ms $P1) $PL $PR OWN_GPROF_CARD=2; same p1_prof2 $S/runs/ab1/base-speed-ids.txt 64
p=$S/prompts/p3k-ids.txt; r p3k_prof2 $p 64 $(ms $p) $PL $PR OWN_GPROF_CARD=2; same p3k_prof2 $S/runs/e52/p3kplain-ids.txt 64
p=$X/x19k-ids.txt; r x19k_prof2 $p 64 $(ms $p) $PL $PR OWN_GPROF_CARD=2; same x19k_prof2 $S/runs/e82/x19k_plain-ids.txt 64
p=$X/x69k-ids.txt; r x69k_dprof2 $p 64 $(ms $p) $PL $PR OWN_GPROF_CARD=2; same x69k_dprof2 $S/runs/e82/x69k_plain-ids.txt 64
p=$X/x69k-ids.txt; r x69k_dprof0 $p 64 $(ms $p) $PL $PR OWN_GPROF_CARD=0; same x69k_dprof0 $S/runs/e82/x69k_plain-ids.txt 64
echo ALLDONE >> $sum
