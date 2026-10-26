#!/bin/bash
# Usage: kbrun.sh BINARY  -- run one microbenchmark on card 27 under the shared lock; checks nodes and kernel log.
set -u
B=$1; O=/dev/shm/ownrt-lab-dexp; LOG=$B.log
[ -e $O/HALT ] && { echo HALT; exit 3; }
exec 9>/dev/shm/card27.lock
flock 9
[ -e $O/HALT ] && { echo HALT; exit 3; }
START=$(date +%s)
env NEOReadDebugKeys=1 FilterBdfPath=0000:27:00.0 ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 ZE_AFFINITY_MASK=0 ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  SYCL_CACHE_DIR=$O/cache/kb-sycl NEO_CACHE_DIR=$O/cache/kb-neo \
  LD_LIBRARY_PATH=/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib \
  nice -n 10 taskset -c 8-15,24-31 $B > $LOG 2>&1 &
P=$!
NODES=""
for i in $(seq 1 300); do sleep 0.1; n=$(ls -l /proc/$P/fd 2>/dev/null | grep -o 'renderD[0-9]*' | sort -u | tr '\n' ' '); [ -n "$n" ] && { NODES=$n; break; }; kill -0 $P 2>/dev/null || break; done
wait $P; RC=$?
sleep 1
F=$(journalctl -k --since "@$START" --no-pager 2>/dev/null | grep -iE "xe .*(fault|reset|error|timed out)|CAT error|GuC")
echo "rc $RC nodes [$NODES] faults [$F]" >> $LOG
[ -n "$F" ] && echo "FAULT kb $B" > $O/HALT
[ -n "$NODES" ] && [ "$NODES" != "renderD131 " ] && echo "foreign node kb $B: $NODES" > $O/HALT
flock -u 9
cat $LOG
