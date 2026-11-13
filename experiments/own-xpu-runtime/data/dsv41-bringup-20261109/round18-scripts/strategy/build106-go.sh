#!/bin/bash
# start build106: HOLD_BUILDS first (helpers' builds wait), then once no other compiler runs, host memory "available"
# >= 6 GiB and no six-card gate runs, for 30 s in a row (one-card helper benches may continue: little host memory)
W=/home/steve/dsv41-work
touch $W/HOLD_BUILDS
q=0
until [ $q -ge 30 ]; do
  if [ $(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo) -ge 6 ] && [ ! -e $W/six.active ] && ! pgrep -x icpx > /dev/null && ! pgrep -x ocloc > /dev/null; then q=$((q+5)); else q=0; fi
  sleep 5
done
$W/build106.sh
rc=$?
rm -f $W/HOLD_BUILDS
exit $rc
