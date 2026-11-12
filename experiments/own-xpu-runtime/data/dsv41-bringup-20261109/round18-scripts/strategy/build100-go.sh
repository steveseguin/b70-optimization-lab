#!/bin/bash
# start build100 once host memory "available" >= 6 GiB, no six-card gate runs and the card locks have been empty
# for 30 s in a row (a build disturbs helper timings)
W=/home/steve/dsv41-work
q=0
until [ $q -ge 30 ]; do
  if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && [ -z "$(ls -A $W/locks 2>/dev/null)" ]; then q=$((q+5)); else q=0; fi
  sleep 5
done
exec $W/build100.sh
