#!/bin/bash
# ce bench: build (one build at a time, >= 6 GiB), then a short six-card run under four copy-path settings.
set -u
W=/home/steve/dsv41-work; C=$W/ce; O=$W/runs/ce; mkdir -p $O; log=$O/lat2.txt
cd $C
set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1; set -u
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)|Fault response'
T0=$(date '+%Y-%m-%d %H:%M:%S')
fchk() { if journalctl -k --since "$T0" -o cat | grep -E "$J" > $O/ce-faults.txt; then echo "FAULT after $1" >> $log; cat $O/ce-faults.txt >> $log; exit 9; fi; }
memok() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
if [ ! -x $C/bcs_lat ]; then
  q=0; until [ $q -ge 20 ]; do
    if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && [ ! -e $W/HOLD_BUILDS ] && ! pgrep -x icpx > /dev/null && ! pgrep -x ocloc > /dev/null; then q=$((q+5)); else q=0; fi; sleep 5; done
  echo "build start $(date +%T)" >> $log
  nice -n 5 icpx -fsycl -O2 -std=c++20 -fsycl-targets=intel_gpu_bmg_g31 bcs_lat.cpp -o bcs_lat -lze_loader >> $log 2>&1 || { echo "BUILD FAILED" >> $log; exit 1; }
  echo "built $(date +%T)" >> $log
fi
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
T0=$(date '+%Y-%m-%d %H:%M:%S')
E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1"
memok; echo "== lat $(date +%T)" >> $log
for a in "2000 4096 1" "2000 4096 2" "2000 16384 1" "2000 16384 2" "2000 65536 1" "2000 65536 2"; do env $E timeout 120 ./bcs_lat $a >> $log 2>&1; echo "exit $?" >> $log; done; env $E timeout 120 ./bcs_lat 2000 256 3 >> $log 2>&1; echo "exit $?" >> $log
fchk bcs
echo "DONE $(date +%T)" >> $log
