#!/bin/bash
# health probe after the 03:30 helper fault (card 0000:a3): six cards, its own clean unit (no engine library path)
W=/home/steve/dsv41-work; O=$W/runs/probe/health-probe-20261111.txt
touch $W/six.active
trap 'rm -f $W/six.active' EXIT
while [ -n "$(ls -A $W/locks 2>/dev/null)" ] || pgrep -f "own_run_v41_" > /dev/null; do sleep 5; done
systemd-run --user --unit=probe89 --wait --collect -p WorkingDirectory=/home/steve/b70-optimization-lab \
  bash -c "timeout 600 scripts/check-qwen36-xpu-xccl-health.sh > $O 2>&1; echo \"rc \$?\" >> $O"
echo "probe89 done $(date +%T)" >> $O
