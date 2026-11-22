#!/bin/bash
# memsample.sh OUT SECONDS: every 0.25 s: time, MemAvailable MemFree Cached AnonPages Mapped Shmem Unevictable SwapFree (MiB), engine RSS (MiB)
out=$1; end=$(( $(date +%s) + ${2:-180} ))
while [ $(date +%s) -lt $end ]; do
  m=$(awk '/^(MemAvailable|MemFree|Cached|AnonPages|Mapped|Shmem|Unevictable|SwapFree|KReclaimable|SUnreclaim|VmallocUsed|PageTables):/ {printf "%s=%d ", $1, $2/1024}' /proc/meminfo)
  pid=$(pgrep -f '^/home/steve/dsv41-work/own_run_v41' | head -1)
  r=$([ -n "$pid" ] && awk '/VmRSS/ {print int($2/1024)}' /proc/$pid/status 2>/dev/null)
  g=$(awk '$1 == "nr_gpu_active" {print int($2 * 4 / 1024)}' /proc/vmstat)
  echo "$(date +%T.%N | cut -c1-12) $m rss=${r:-0} gpu=${g:-0}" >> $out
  sleep 0.25
done
