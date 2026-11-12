#!/bin/bash
# start build101 after gate tg100 has ended, then once host memory "available" >= 6 GiB, no six-card gate runs and
# the card locks have been empty for 30 s in a row (a build disturbs helper timings)
W=/home/steve/dsv41-work
while systemctl --user is-active --quiet tg100; do sleep 15; done
# then the short overlap check (gate_xov2, unit xov2) unless build101.nowait exists
until grep -qE "ALLDONE|STOP" $W/runs/xov2/summary.txt 2>/dev/null || [ -e $W/build101.nowait ]; do sleep 15; done
while systemctl --user is-active --quiet xov2; do sleep 15; done
q=0
until [ $q -ge 30 ]; do
  if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && [ -z "$(ls -A $W/locks 2>/dev/null)" ]; then q=$((q+5)); else q=0; fi
  sleep 5
done
exec $W/build101.sh
