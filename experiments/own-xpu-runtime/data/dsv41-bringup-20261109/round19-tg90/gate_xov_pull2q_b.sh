#!/bin/bash
# gate_xov_pull2q (plan item E, step 1; SIX-CARD: the main thread runs it between gates, never a helper):
# does a pull exchange on a second queue per card hide behind compute on all six cards, with 0 wrong values?
#   1. xov_pull2q_test 400: the two-half pattern at the engine's half-block shapes (32 and 128 tokens), pulls built
#      for 128 and 256 registers, every gathered row checked; then the time per iteration compute only / one
#      queue / two queues and the hidden fraction (compute kernels of 128 and 256 registers, pulls of 16 / 64 groups)
#   2. xov_pull2q_test 8 stuck: card 5 stops issuing exchanges half way; the five others must report the timeout (err word)
#      within ~1 s each, and the run must end (no hang)
# Decision (design.md sections 1 and 6): go to the engine patch only if part 1 has 0 wrong values / 0 timeouts and the
# hidden fraction is >= 60 % for the shapes with compute and pulls in the same register mode (the engine's case
# after pinning the pulls to the surrounding kernels' mode), and part 2 reports the timeout on 5 of 5 cards.
set -u
W=/home/steve/dsv41-work
X=$W/xov
E=/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/engine
D=$W/runs/xov1
mkdir -p $D
sum=$D/summary.txt
export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
fcheck() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | grep -vE '^\{[0-9]+\}\[Hardware Error\]')
  [ -z "$f" ] && return 0; echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
while pgrep -f build_pull2q.sh > /dev/null; do sleep 5; done # the helper's own compile of the test (one at a time)
if [ ! -x $X/xov_pull2q_test ]; then # one compile, nice 10, only with >= 6 GiB available
  [ "$(awk '/MemAvailable/ {print int($2 / 1048576)}' /proc/meminfo)" -ge 6 ] || { echo STOP_MEM >> $sum; exit 1; }
  (cd $X && nice -n 10 icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
     -Wno-deprecated-declarations -I $E/src xov_pull2q_test.cpp -o xov_pull2q_test -lze_loader) > $D/build.log 2>&1 \
    || { echo STOP_BUILD >> $sum; exit 1; }
fi
SP=
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
for k in "p1|400" "stuck|8 stuck"; do
  IFS='|' read -r name args <<< "$k"; t0=$(date '+%Y-%m-%d %H:%M:%S')
  timeout 300 env NEOReadDebugKeys=1 DisableIndirectAccess=1 $X/xov_pull2q_test $args > $D/$name.log 2>&1
  echo "$name exit $?" >> $sum
  grep -E "wrong values|hidden|report a timeout|PASS|FAIL" $D/$name.log | sed "s/^/$name: /" >> $sum
  fcheck "$t0"
done
echo ALLDONE >> $sum
