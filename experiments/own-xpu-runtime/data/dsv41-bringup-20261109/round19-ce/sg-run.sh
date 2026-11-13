#!/bin/bash
# sg bench: two builds (SIMD16 / SIMD32), short six-card runs. One build at a time.
set -u
W=/home/steve/dsv41-work; C=$W/ce; O=$W/runs/ce; log=$O/sg.txt
cd $C; set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1; set -u
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)|Fault response'
for sg in 16 32; do
  q=0; until [ $q -ge 20 ]; do
    if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && [ ! -e $W/HOLD_BUILDS ] && ! pgrep -x icpx > /dev/null && ! pgrep -x ocloc > /dev/null; then q=$((q+5)); else q=0; fi; sleep 5; done
  echo "build sg$sg $(date +%T)" >> $log
  nice -n 5 icpx -fsycl -O2 -std=c++20 -DSG=$sg -fsycl-targets=intel_gpu_bmg_g31 xchg_sg.cpp -o xchg_sg$sg -lze_loader >> $log 2>&1 || { echo "BUILD FAILED" >> $log; exit 1; }
done
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
T0=$(date '+%Y-%m-%d %H:%M:%S')
E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1"
for sg in 16 32; do echo "== sg$sg $(date +%T)" >> $log; env $E timeout 200 ./xchg_sg$sg 16,64,640 20 >> $log 2>&1; echo "exit $?" >> $log; sleep 3; done
journalctl -k --since "$T0" -o cat | grep -E "$J" >> $log && echo "FAULT" >> $log
echo "DONE $(date +%T)" >> $log
