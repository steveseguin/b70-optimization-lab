#!/usr/bin/env bash
# Room census (campaign 42): every 30 s, the memory breakdown of each server process (smaps_rollup + VmSwap) and the
# other large processes; once a minute after the arm starts, the ten largest anonymous mappings of one worker.
# Small reads only (a few KB per process). Runs as root via sudo -A. Stops when $OUT/STOP exists.
OUT=$1; mkdir -p "$OUT"
n=0
while [[ ! -e $OUT/STOP ]]; do
  ts=$(date +%T)
  {
    echo "## $ts $(grep -E '^(MemAvailable|AnonPages|Cached|Shmem|SwapCached|GPUActive|SUnreclaim):' /proc/meminfo | awk '{printf "%s=%dM ", $1, $2/1024}')"
    for pid in $(ps -eo pid=,comm= | awk '$2 ~ /^(VLLM::|vllm|harbor|python3|claude|codex|dockerd|containerd|update-manag)/ {print $1}'); do
      c=$(cat /proc/$pid/comm 2>/dev/null) || continue
      r=$(awk '/^(Rss|Anonymous|Shared_Clean|Shared_Dirty|Private_Clean|Private_Dirty|Swap|Locked):/ {printf "%s=%dM ", $1, $2/1024}' /proc/$pid/smaps_rollup 2>/dev/null)
      echo "$pid $c $r"
    done
  } >> "$OUT/rollup.txt"
  n=$((n+1))
  if (( n % 2 == 0 )); then
    w=$(ps -eo pid=,comm= | awk '$2 ~ /^VLLM::Worker/ {print $1; exit}')
    if [[ -n $w ]]; then
      { echo "## $ts worker $w top anonymous mappings (KB anon, KB rss, range, name)"
        awk '/^[0-9a-f]+-[0-9a-f]+ / {range=$1; name=$6} /^Anonymous:/ {a[range" "name]+=$2} /^Rss:/ {r[range" "name]=$2}
             END {for (k in a) if (a[k] > 20000) print a[k], r[k], k}' /proc/$w/smaps 2>/dev/null | sort -rn | head -10
        awk '/^[0-9a-f]+-[0-9a-f]+ / {name=($6==""?"[anon]":$6)} /^Anonymous:/ {a[name]+=$2} END {for (k in a) print a[k], k}' /proc/$w/smaps 2>/dev/null | sort -rn | head -8 | sed 's/^/by-name /'
      } >> "$OUT/worker-maps.txt"
    fi
  fi
  sleep 30
done
