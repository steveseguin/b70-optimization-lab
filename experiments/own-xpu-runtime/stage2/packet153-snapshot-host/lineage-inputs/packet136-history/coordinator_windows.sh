#!/usr/bin/env bash
# Coordinator only, already inside an admitted nice-0 unit on cores 0-3,16-19.
# --resume-from <stopped-chain> imports only pinned early evidence; starts at KD.
set -euo pipefail
packet49=experiments/own-xpu-runtime/stage2/packet97-record-bundle
exec python3 -B "$packet49/queue_runner.py" --authorized-device-window "$@"
