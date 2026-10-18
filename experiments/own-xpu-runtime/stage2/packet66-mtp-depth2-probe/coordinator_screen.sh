#!/usr/bin/env bash
# Coordinator entry only: running this file starts the device screen.
set -euo pipefail
cd /home/steve/llm-optimizations
: "${1:?fresh reviewed fault receipt required}"
: "${P49_LDP:?coordinator must export the approved library path}"
P=experiments/own-xpu-runtime/stage2/packet66-mtp-depth2-probe
V=experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes
exec env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
  /usr/bin/python3 -B "$V/screen.py" --profile tp2 --lane B --placement 1-split23 \
  --lineage "$P" --seal "$P/screen-seal.json" --binary "$P/build/device/own-rt-iq3" \
  --dispatch "$P/dispatch-speed6.json" --authorized-device-window --fault-review "$1" \
  --output "$V/evidence/packet66-B-01" < /dev/null
