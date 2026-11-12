#!/bin/bash
# peer-exchange benches before / after iommu=pt (2026-11-12). usage: pt-bench.sh TAG (before | after)
# Short six-card runs only (seconds each), fault grep after each, stop at the first fault line.
set -u
W=/home/steve/dsv41-work; P=$W/pt; O=$W/runs/pt; TAG=$1
cd $P
set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1; set -u
J='PCIe Bus Error|AER:|Hardware Error|Machine check|xe .*(fault|reset|hang|timeout)|GuC.*(fail|reset)|Fault response'
T0=$(date '+%Y-%m-%d %H:%M:%S')
log=$O/bench-$TAG.txt
echo "pt-bench $TAG start $(date +%T); cmdline: $(cat /proc/cmdline); card iommu domain: $(cat /sys/bus/pci/devices/0000:03:00.0/iommu_group/type)" >> $log
fchk() { if journalctl -k --since "$T0" -o cat | grep -E "$J" > $O/bench-$TAG-faults.txt; then echo "FAULT after $1" >> $log; cat $O/bench-$TAG-faults.txt >> $log; exit 9; fi; }
memok() { local i=0; until [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 7 ] || [ $i -ge 120 ]; do sleep 5; i=$((i+1)); done; }
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active; trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "^/home/steve/dsv41-work/own_run_v41" > /dev/null || pgrep -x icpx > /dev/null || pgrep -x ocloc > /dev/null; do sleep 10; done
if [ ! -x $P/xchg_bw_bench ]; then
  memok
  icpx -fsycl -O2 -std=c++20 xchg_bw_bench.cpp -o xchg_bw_bench -lze_loader >> $log 2>&1 || { echo "BUILD FAILED" >> $log; exit 1; }
  echo "built xchg_bw_bench $(date +%T)" >> $log
fi
memok
echo "== bw (16,64,160,640 KiB slices, 30 reps)" >> $log
env ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 timeout 300 ./xchg_bw_bench 16,64,160,640 30 >> $log 2>&1; echo "exit $?" >> $log
fchk bw
sleep 5; memok
echo "== direct ipc g16 (a2a, pair; 3456/7296/9728 B)" >> $log
env ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 EnableDeferBacking=0 timeout 300 ./xchg_direct_bench --ctx=ipc --topos=a2a,pair --forms=fresh --sizes=3456,7296,9728 --wg=16 --reps=5 > $O/direct-ipc-g16-$TAG.txt 2>&1; echo "exit $?" >> $log
grep -A4 "^VERDICT" $O/direct-ipc-g16-$TAG.txt >> $log
fchk direct-ipc
sleep 5; memok
echo "== direct shared (default shapes)" >> $log
env ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 EnableDeferBacking=0 timeout 300 ./xchg_direct_bench > $O/direct-shared-$TAG.txt 2>&1; echo "exit $?" >> $log
grep -A5 "^VERDICT" $O/direct-shared-$TAG.txt >> $log
fchk direct-shared
echo "pt-bench $TAG DONE $(date +%T)" >> $log
