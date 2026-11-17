#!/bin/bash
# chainq140 (2026-11-17 06:20; replaces chainq139: a16a2b5f18 = + idxfilt-2c): after c128b (the 1M follow-up, tp128): idxfilt-2's bench alone first (compile from
# a16a2b5f18, run on card 1: 95K / 352K / 993K prompt shapes, then check shapes 6 / 3 tokens); only if it PASSes: build
# tp129 (f5f7041c74) -> c129 (bench, dump, check mode x95k_f2, speed x95k / x200k / x1m with OWN_IDX_FILT=1).
# A bench failure stops the queue for a fix; a failed preflight or a kernel fault line stops it too.
W=/home/steve/dsv41-work; log=$W/chainq118.txt
say() { echo "$(date '+%F %T') $*" >> $log; sync -f $log; }
while systemctl --user is-active -q c128b; do sleep 20; done
s=$(ls -td $W/runs/c128b-*/ 2>/dev/null | head -1)summary.txt
say "c128b ended: $(tail -1 $s 2>/dev/null | cut -c1-200)"
grep -qE "^STOP .*(kernel|preflight)" $s 2>/dev/null && { say "queue stopped: c128b fault"; exit 1; }
while [ -e $W/six.active ]; do sleep 20; done
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
C=a16a2b5f18; S=$W/src129b; D=$W/runs/tif1; mkdir -p $D
touch $W/locks/build-tif1
rm -rf $S; mkdir -p $S
git -C $W/tp121 archive $C:experiments/own-xpu-runtime/engine src tools/bench | tar -x -C $S
GPU="-fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31"
if ! (cd $S && nice -n 5 icpx -fsycl $GPU "-exclude_ir -options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_idxfilt.cpp -o $W/test_idxfilt_tif1 > $D/build.log 2>&1); then
  rm -f $W/locks/build-tif1; say "tif1: the idxfilt-2 bench did not compile ($D/build.log): queue stopped for a fix"; exit 1; fi
rm -f $W/locks/build-tif1
say "tif1: bench built from $C"
source $W/stable/stable.env
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check|watchdog: BUG|rcu_sched self-detected|AMD-Vi: Event|wedged|inaccessible|GuC'
t0=$(date '+%F %T')
ok=1
for cs in "43 95000,352000,993000 p" "6 33000,166000 c6" "3 166000 c3"; do
  set -- $cs
  env BENCH_M=$1 BENCH_LENS=$2 ONEAPI_DEVICE_SELECTOR=level_zero:1 timeout 1500 $W/test_idxfilt_tif1 > $D/$3.log 2>&1; rc=$?
  say "tif1 $3 (m $1, $2): exit $rc, $(tail -1 $D/$3.log | cut -c1-120)"
  tail -1 $D/$3.log | grep -q '^PASS' || ok=0
  f=$(journalctl -k --since "$t0" -o cat | grep -iE "$J" | head -3)
  [ -n "$f" ] && { say "queue stopped: kernel line during tif1: $f"; exit 1; }
  [ $ok = 1 ] || break
done
[ $ok = 1 ] || { say "tif1: the idxfilt-2 bench did not pass: queue stopped for a fix"; exit 1; }
say "chainq140: building tp129"
bash $W/build129.sh
say "tp129 built: $(grep 'source commit' $W/build-tp129.log | tail -1); $(tail -1 $W/build-tp129.log)"
grep -qE "source commit (a16a2b5f18|f5f7041c74)" $W/build-tp129.log && grep -q "tp129 build exit 0" $W/build-tp129.log || { say "chainq140: tp129 is not $C: c129 not started"; exit 1; }
sleep 10; say "starting c129"; bash $W/c129.sh
s=$(ls -td $W/runs/c129-*/ | head -1)summary.txt
say "c129 ended: $(tail -1 $s | cut -c1-200)"
say "chainq140 done"
