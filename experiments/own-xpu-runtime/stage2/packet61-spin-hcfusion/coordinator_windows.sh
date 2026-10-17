#!/usr/bin/env bash
# Coordinator only, already inside an admitted nice-0 unit on cores 0-3,16-19.
set -euo pipefail
packet49=experiments/own-xpu-runtime/stage2/packet61-spin-hcfusion
exec python3 -B "$packet49/queue_runner.py" --authorized-device-window "$@"
