#!/bin/bash
set -uo pipefail
cd /dev/shm/ownrt-lab-ctx64k
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
for arm in batched tbt; do
  start=$(date +%s)
  extra=""; [ $arm = batched ] && extra="--batched --rows 32"
  nice -n 10 taskset -c 8-15,24-31 python3 -B $D run --launch rank1-card27-s24-ctx65536-launch.json --out /dev/shm/ownrt-lab-ctx64k/run-60k-$arm --steps 48 --prompt 60000 $extra --cache /dev/shm/ownrt-lab-ctx64k/cache || { echo "ARM $arm FAILED"; exit 1; }
  journalctl -k --since "@$start" --no-pager | grep -iE "xe .*(fault|reset|error|timed out)|CAT error|GuC" && { echo "KERNEL FAULT after $arm"; exit 2; }
  echo "ARM $arm done $(( $(date +%s) - start )) s"
done
python3 -B $D compare /dev/shm/ownrt-lab-ctx64k/run-60k-batched /dev/shm/ownrt-lab-ctx64k/run-60k-tbt; echo "compare rc=$?"
