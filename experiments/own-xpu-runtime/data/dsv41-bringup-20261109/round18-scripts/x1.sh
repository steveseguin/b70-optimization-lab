#!/bin/bash
# x1: are the card-to-card exchanges slower since the 15:16 reset because each card's DMA addresses are still
# allocated below 4 GiB? (The boot before had "Using 46-bit DMA addresses" for five cards from 2026-11-09 15:32;
# boot 0 has none; r1's prompt-1 profile has XchgPull 11.63 -> 12.84 us and XchgP 5.90 -> 7.11 us per launch vs
# e83, the compute kernels the same.) Builds xchg_lat_bench and iova_wide, then: before = the exchange bench,
# prompt-1 speed with tp74 defaults twice, guessing on code / analysis, a card-2 answer profile; iova_wide (each
# card maps 5 GiB of a neighbour's memory: the 32-bit first try fails and the card's later mappings go above
# 4 GiB for the rest of the boot); after = the same again. Stops at the first fault line.
set -u
W=/home/steve/dsv41-work
L=/home/steve/b70-optimization-lab
E=$L/experiments/own-xpu-runtime/engine
D=$W/runs/x1
mkdir -p $D
sum=$D/summary.txt; marks=$D/marks.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
t0=$(date +%s)
mkdir -p $W/srcx1/tools/bench; cp $E/tools/bench/xchg_lat_bench.cpp $E/tools/bench/iova_wide.cpp $W/srcx1/tools/bench/; cp -a $E/src $W/srcx1/
(cd $W/srcx1 && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -Wno-deprecated-declarations -I src tools/bench/xchg_lat_bench.cpp -o $W/xchg_lat_bench -lze_loader > $W/build-x1-bench.log 2>&1); r1=$?
(cd $W/srcx1 && icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -Wno-deprecated-declarations tools/bench/iova_wide.cpp -o $W/iova_wide -lze_loader > $W/build-x1-iova.log 2>&1); r2=$?
echo "builds: xchg_lat_bench $r1, iova_wide $r2 in $(( $(date +%s) - t0 )) s" >> $sum
[ $r1 -eq 0 ] && [ $r2 -eq 0 ] || { echo STOP_BUILD >> $sum; exit 1; }
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
mono() { python3 -I -c 'import time; print(f"{time.monotonic():.4f}")'; }
fcheck() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | head -3); [ -n "$f" ] && { echo "$f" | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }; return 0; }
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
trap 'kill $SP 2>/dev/null' EXIT
G="OWN_MT_EU=6 OWN_MT_TGU=2 OWN_MT_RIDE=1 OWN_MT_RWG=128 OWN_MT_RFUSE=1 OWN_HC_FIN=1"
PL="OWN_TP=6 OWN_PROMPT_BLOCK=16 OWN_MT_TG=4 OWN_MT_TG_MAX=16 $G"
BEST="$PL OWN_MT_TGM=1:1,2:1,3:3,4:2,5:3,6:3 OWN_SPEC=5 OWN_SPEC_TAU=0.5 OWN_SPEC_KMIN=0 OWN_MT_TGR=2:4,3:4,4:4,5:4,6:4 OWN_MT_TGR_ROWS=4096"
PR="OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=2"
PP=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/spec-prompts
P1=$L/experiments/own-xpu-runtime/data/dsv41-bringup-20261109/prompt1-ids.txt
DS=/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
r() { local name=$1 pr=$2 nt=$3 eos=$4 out=$5; shift 5; local t0; t0=$(date '+%Y-%m-%d %H:%M:%S')
  echo "$name start $(mono)" >> $marks
  env "$@" OWN_PROMPT=$pr OWN_EOS=$eos $W/own_run_v41_tp74 - $nt $out 4096 > $D/$name.log 2>&1
  local rc=$?
  echo "$name end $(mono)" >> $marks
  echo "$name exit $rc" >> $sum
  grep -h "prompt:\|decode:\|spec decode\|host io\|rror\|timed out\|exceeds\|SAME AS\|DIFFERS" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
  [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
bench() { local t0; t0=$(date '+%Y-%m-%d %H:%M:%S'); echo "bench_$1 start $(mono)" >> $marks
  NEOReadDebugKeys=1 DisableIndirectAccess=1 $W/xchg_lat_bench 2000 > $D/bench_$1.txt 2>&1; local rc=$?
  echo "bench_$1 end $(mono)" >> $marks; echo "bench_$1 exit $rc" >> $sum; fcheck "$t0"; [ $rc -eq 0 ] || { echo STOP_EXIT >> $sum; exit 1; }; }
phase() { local s=$1
  bench $s
  for i in 1 2; do r p1${s}$i $P1 128 -1 $D/p1${s}$i-ids.txt $PL
    cmp -s $D/p1${s}$i-ids.txt $W/runs/ab1/base-speed-ids.txt && echo "p1${s}$i SPEED128_SAME" >> $sum || echo "p1${s}$i SPEED128_DIFFER" >> $sum; done
  for n in code analysis; do r ${n}_$s $PP/$n-ids.txt 512 1 $D/${n}_$s-ids.txt $BEST OWN_VERIFY_REF=$W/runs/e57/${n}_plain-ids.txt OWN_DSPARK=$DS; done
  r p1${s}_prof $P1 64 -1 $D/p1${s}_prof-ids.txt $PL $PR
  sed -n '/GPU-time profile/,$p' $D/p1${s}_prof.log > $D/p1${s}-decode-profile-card2.txt; }
echo "46-bit lines before: $(journalctl -b -k -o cat | grep -c 'Using 46-bit DMA addresses')" >> $sum
phase b
t1=$(date '+%Y-%m-%d %H:%M:%S')
$W/iova_wide 5 > $D/iova_wide.txt 2>&1; echo "iova_wide exit $?" >> $sum
fcheck "$t1"
echo "46-bit lines after: $(journalctl -b -k -o cat | grep -c 'Using 46-bit DMA addresses')" >> $sum
journalctl -b -k -o cat | grep 'Using 46-bit DMA addresses' >> $sum
grep -q "46-bit DMA addresses" $D/iova_wide.txt || { echo STOP_NOSWITCH >> $sum; exit 1; }
phase a
grep -c "SAME AS the plain" $sum | sed 's/^/guessing SAME count: /' >> $sum
echo ALLDONE >> $sum
