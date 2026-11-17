#!/bin/bash
# vramlog.sh OUT HOURS: every 10 s while an engine runs, its card memory in VRAM per card (KiB, from
# /proc/PID/fdinfo drm-total-vram0; cards in PCI order); quiet when none runs; ends after HOURS or when OUT.stop exists
out=$1; end=$(( $(date +%s) + ${2:-6} * 3600 ))
while [ $(date +%s) -lt $end ] && [ ! -e $out.stop ]; do
  pid=$(pgrep -f '^/home/steve/dsv41-work/own_run_v41' | head -1)
  if [ -n "$pid" ]; then
    line=$(for f in /proc/$pid/fdinfo/*; do awk '/drm-pdev/ {p=$2} /drm-total-vram0/ {v=$2} END {if (v > 1000000) print p, v}' $f 2>/dev/null; done | sort | awk '{printf "%s ", $2}')
    [ -n "$line" ] && echo "$(date +%T) $pid $line" >> $out
  fi
  sleep 10
done
