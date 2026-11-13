#!/bin/bash
# bcs_sync: build, then one-card run on card 2 or whichever is free (takes six.active to stay out of everyone's way; seconds)
set -u
W=/home/steve/dsv41-work; C=$W/ce; O=$W/runs/ce; log=$O/sync.txt
cd $C; set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1; set -u
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)|Fault response'
q=0; until [ $q -ge 20 ]; do
  if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && [ ! -e $W/HOLD_BUILDS ] && ! pgrep -x icpx > /dev/null && ! pgrep -x ocloc > /dev/null; then q=$((q+5)); else q=0; fi; sleep 5; done
echo "build start $(date +%T)" >> $log
nice -n 5 icpx -fsycl -O2 -std=c++20 -fsycl-targets=intel_gpu_bmg_g31 bcs_sync.cpp -o bcs_sync -lze_loader >> $log 2>&1 || { echo "BUILD FAILED" >> $log; exit 1; }
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
T0=$(date '+%Y-%m-%d %H:%M:%S'); echo "== sync $T0" >> $log
env ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 timeout 120 ./bcs_sync 0 >> $log 2>&1; echo "exit $?" >> $log
journalctl -k --since "$T0" -o cat | grep -E "$J" >> $log && echo "FAULT" >> $log
echo "DONE $(date +%T)" >> $log
