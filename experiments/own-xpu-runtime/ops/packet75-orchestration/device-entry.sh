#!/bin/bash
set -euo pipefail
cd /home/steve/llm-optimizations
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet75-orchestration/verify_ready.py </dev/null
exec python3 -B experiments/own-xpu-runtime/stage2/packet75-record-bundle/queue_runner.py --authorized-device-window --output-root /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet75-record-bundle/build/device-cards01-a </dev/null >> experiments/own-xpu-runtime/ops/packet75-orchestration/chain.log 2>&1
