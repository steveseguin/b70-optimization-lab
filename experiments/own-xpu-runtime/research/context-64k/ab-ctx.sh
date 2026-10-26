#!/bin/bash
set -uo pipefail
cd /dev/shm/ownrt-lab-ctx64k
D=/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/tools/tp_rank1_driver.py
for ctx in 4096 65536; do
  start=$(date +%s)
  nice -n 10 taskset -c 8-15,24-31 python3 -B $D run --launch rank1-card27-s24-ctx$ctx-launch.json --out /dev/shm/ownrt-lab-ctx64k/run-s24-ctx$ctx --steps 48 --prompt 300 --cache /dev/shm/ownrt-lab-ctx64k/cache || { echo "ARM $ctx FAILED"; exit 1; }
  journalctl -k --since "@$start" --no-pager | grep -iE "xe .*(fault|reset|error|timed out)|CAT error|GuC" && { echo "KERNEL FAULT after $ctx"; exit 2; }
done
python3 -B compare_ctx.py run-s24-ctx4096 run-s24-ctx65536; echo "compare rc=$?"
