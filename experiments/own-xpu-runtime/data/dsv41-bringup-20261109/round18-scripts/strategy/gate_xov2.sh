#!/bin/bash
# gate_xov2 (overlap plan, README-overlap.txt section 6; SIX-CARD: the coordinator runs it, never a helper).
# One layer's order of two half-blocks with all eight pulls on a second queue per card, each pull in the register mode
# of the compute beside it, every gathered row checked. Three short runs, 30 s apart; each run has ~5-8 s of six-card
# exchange traffic and stops itself after 25 s at most (STOP_TIME). No deliberately stuck exchange.
#   d128  decision run (128-token halves, blocks of 256): 60-layer check + timings + per-site hidden shares
#   d64   the same for 64-token halves (blocks of 128)
#   c     the remaining checks (today's pull form on two queues and on one queue, both sizes)
# Results: runs/xov2/summary.txt (+ d128.log, d64.log, c.log, telemetry.smp). The decision line is the summary's
# "DECISION:" line ("half 128 two queues E16 ..."). Stops at the first run that fails or leaves a kernel-log fault line.
set -u
W=/home/steve/dsv41-work
P=$W/pb256
D=$W/runs/xov2
mkdir -p $D
sum=$D/summary.txt
export LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib ZES_ENABLE_SYSMAN=1
J='fault response|cat error|engine reset|coredump has been created|gt reset|timedout job|exec queue reset|suspend fence|vm worker error|reset started|PCIe Bus Error|AER:|Hardware Error|Machine check'
fcheck() { local f; f=$(journalctl -k --since "$1" -o cat | grep -iE "$J" | grep -vE '^\{[0-9]+\}\[Hardware Error\]')
  [ -z "$f" ] && return 0; echo "$f" | head -3 | sed 's/^/FAULT: /' >> $sum; echo STOP_FAULT >> $sum; exit 1; }
[ -x $P/bin/xov2_layer_test ] || { echo STOP_NOBIN >> $sum; exit 1; }
[ $P/bin/xov2_layer_test -nt $P/xov2_layer_test.cpp ] || { echo STOP_STALE_BIN >> $sum; exit 1; } # (rebuilt after the last edit)
SP=
touch $W/six.active
trap 'rm -f $W/six.active; [ -n "$SP" ] && kill $SP 2>/dev/null' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f own_run_v41 > /dev/null; do sleep 10; done
python3 -I $W/tools/gpu_sampler.py $D/telemetry.smp 0.05 &
SP=$!
first=1
for name in d128 d64 c; do
  [ $first = 1 ] || sleep 30
  first=0
  t0=$(date '+%Y-%m-%d %H:%M:%S')
  timeout 60 env NEOReadDebugKeys=1 DisableIndirectAccess=1 $P/bin/xov2_layer_test $name 60 > $D/$name.log 2>&1
  rc=$?
  echo "$name exit $rc ($t0)" >> $sum
  grep -E "busy kernels|wrong values|per layer|per site|site X|STOP_TIME|PASS|FAIL" $D/$name.log | sed "s/^/$name: /" >> $sum
  [ $name = d128 ] && grep -E "^half 128 two queues E16" $D/$name.log | sed 's/^/DECISION: /' >> $sum
  fcheck "$t0"
  [ $rc = 0 ] || { echo STOP_RUN >> $sum; exit 1; }
done
echo ALLDONE >> $sum
