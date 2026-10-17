#!/usr/bin/env bash
# Run only inside a coordinator-owned screen-* user unit after admission.
set -euo pipefail
cd /home/steve/llm-optimizations
: "${1:?fresh reviewed fault receipt required}"
: "${P49_LDP:?approved coordinator library path required}"
P=experiments/own-xpu-runtime/stage2/packet68b-batched-rows
exec env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
 /usr/bin/python3 -B "$P/screen_probe.py" --profile tp2 --lane B --placement 1 \
 --lineage "$P" --seal "$P/screen-seal.json" --binary "$P/build/device/own-rt-iq3" \
 --dispatch "$P/dispatch-speed6.json" --authorized-device-window --fault-review "$1" \
 --output "experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes/evidence/packet68b-batched-B-01" </dev/null
