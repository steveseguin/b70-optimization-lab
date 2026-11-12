#!/bin/bash
# health probe after the 01:13 host reset (machine check, Bank 5), first thing after boot; six cards, own clean unit
W=/home/steve/dsv41-work; O=$W/runs/probe/health-probe-20261112T0113.txt
until [ ! -e $W/six.active ]; do sleep 5; done
touch $W/six.active
trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "own_run_v41_" > /dev/null; do sleep 5; done
systemd-run --user --unit=probe0113run --wait --collect -p WorkingDirectory=/home/steve/b70-optimization-lab \
  bash -c "timeout 600 scripts/check-qwen36-xpu-xccl-health.sh > $O 2>&1; echo \"rc \$?\" >> $O"
echo "probe0113 done $(date +%T)" >> $O
cp $O $W/faults/reset-20261112T0113/
