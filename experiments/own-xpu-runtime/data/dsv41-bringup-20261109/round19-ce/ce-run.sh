#!/bin/bash
# ce bench: build (one build at a time, >= 6 GiB), then a short six-card run under four copy-path settings.
set -u
W=/home/steve/dsv41-work; C=$W/ce; O=$W/runs/ce; mkdir -p $O; log=$O/ce.txt
cd $C
set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1; set -u
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)|Fault response'
T0=$(date '+%Y-%m-%d %H:%M:%S')
fchk() { if journalctl -k --since "$T0" -o cat | grep -E "$J" > $O/ce-faults.txt; then echo "FAULT after $1" >> $log; cat $O/ce-faults.txt >> $log; exit 9; fi; }
memok() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
if [ ! -x $C/xchg_ce_bench ]; then
  q=0; until [ $q -ge 20 ]; do
    if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && [ ! -e $W/HOLD_BUILDS ] && ! pgrep -x icpx > /dev/null && ! pgrep -x ocloc > /dev/null; then q=$((q+5)); else q=0; fi; sleep 5; done
  echo "build start $(date +%T)" >> $log
  nice -n 5 icpx -fsycl -O2 -std=c++20 -fsycl-targets=intel_gpu_bmg_g31 xchg_ce_bench.cpp -o xchg_ce_bench -lze_loader >> $log 2>&1 || { echo "BUILD FAILED" >> $log; exit 1; }
  echo "built $(date +%T)" >> $log
fi
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
T0=$(date '+%Y-%m-%d %H:%M:%S')
E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1"
for v in "default:" "d2d-ce:UR_L0_USE_COPY_ENGINE_FOR_D2D_COPY=1" "inorder-ce:UR_L0_USE_COPY_ENGINE_FOR_IN_ORDER_QUEUE=1 UR_L0_USE_COPY_ENGINE_FOR_D2D_COPY=1" "no-ce:UR_L0_USE_COPY_ENGINE=0"; do
  memok; tag=${v%%:*}; ev=${v#*:}
  echo "== $tag ($ev) $(date +%T)" >> $log
  env $E $ev timeout 300 ./xchg_ce_bench 64,640,4096 20 >> $log 2>&1; echo "exit $?" >> $log
  fchk $tag; sleep 3
done
echo "DONE $(date +%T)" >> $log
