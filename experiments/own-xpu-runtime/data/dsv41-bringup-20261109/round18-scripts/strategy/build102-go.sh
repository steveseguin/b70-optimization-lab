#!/bin/bash
# start build102 after the health probe (unit probe2124) has finished and passed, then once host memory "available"
# >= 6 GiB, no six-card gate runs and the card locks have been empty for 30 s in a row
W=/home/steve/dsv41-work
until [ -e $W/runs/probe/health-probe-20261111T2124.txt ] && grep -q "probe2124 done" $W/runs/probe/health-probe-20261111T2124.txt; do sleep 15; done
grep -q "^rc 0" $W/runs/probe/health-probe-20261111T2124.txt || { echo "tp102 build exit 7 (probe failed)" >> $W/build-tp102.log; exit 7; }
q=0
until [ $q -ge 30 ]; do
  if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && [ -z "$(ls -A $W/locks 2>/dev/null)" ]; then q=$((q+5)); else q=0; fi
  sleep 5
done
exec $W/build102.sh
