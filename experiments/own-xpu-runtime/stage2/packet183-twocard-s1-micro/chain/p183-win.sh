#!/bin/bash
# p183-win.sh - packet183 win-path waiter entry. PREPARED, NOT ARMED (arming: chain/ARMING.md).
# Thin systemd-unit entry for chain/p183_win.py (all logic, guards and exit codes are there):
# exit 0 = no confirmation needed (or confirmation finished), 2 = bracket not DONE/no summary,
# 3 = deadline, 4 = derived input refused, 5 = an owner endpoint is active, 6 = markers busy,
# 7 = host memory/storage admission refused, 8 = confirmation produced no passed summary,
# 9 = confirmation client deadline. Never queues, never deletes PAUSE files, never restarts.
set -u
cd "${P183_REPO:-/home/steve/llm-optimizations}"
exec nice -n 19 taskset -c 8-15,24-31 /usr/bin/python3 -B experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/chain/p183_win.py </dev/null
