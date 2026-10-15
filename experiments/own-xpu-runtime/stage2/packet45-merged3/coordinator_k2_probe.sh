#!/usr/bin/env bash
# Coordinator-only diagnostic chain. Run from repo root, nice-0 parent.
# No target device execution is performed by the preparation agent.
set -euo pipefail
[[ ${PACKET45_DIAGNOSTIC_UNSEALED:-0} == 1 ]] || { echo "PACKET45_DIAGNOSTIC_UNSEALED=1 required" >&2; exit 2; }
[[ ${1:-} == --mtp-k2-probe ]] || { echo "explicit --mtp-k2-probe required" >&2; exit 2; }
probe_card=${2:?first card (0 or 2)}
[[ $probe_card == 0 || $probe_card == 2 ]] || { echo "card must be 0 or 2" >&2; exit 2; }
packet45=experiments/own-xpu-runtime/stage2/packet45-merged3
probe_out=${3:?new output directory below packet build/}
probe_suite=${4:-experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json}
# Read the opt-in before env -i. Never pass unadmitted environment keys to ranks.
probe_common=(ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2
  LD_LIBRARY_PATH="${LD_LIBRARY_PATH:?coordinator library path required}" python3 -B "$packet45/window.py"
  --authorized-device-window --diagnostic-unsealed --card "$probe_card"
  --context 4096 --draft-rank 1 --target-split 23)
probe_k=(nice -n 19 "${probe_common[@]}")
"${probe_k[@]}" --window K0 --output "$probe_out/K0"
"${probe_k[@]}" --window K1a --output "$probe_out/K1a" --k0 "$probe_out/K0/window.json" --dispatch "$packet45/dispatch-p45.json"
"${probe_k[@]}" --window K1b --output "$probe_out/K1b" --k0 "$probe_out/K0/window.json" --k1a "$probe_out/K1a/window.json" --dispatch "$packet45/dispatch-p45.json"
"${probe_k[@]}" --window K2 --output "$probe_out/K2" --k0 "$probe_out/K0/window.json" --k1a "$probe_out/K1a/window.json" --k1b "$probe_out/K1b/window.json" --dispatch "$packet45/dispatch-p45.json" --seconds 14400
"${probe_common[@]}" --window W0p --output "$probe_out/W0p" --k0 "$probe_out/K0/window.json"
"${probe_k[@]}" --window KD --output "$probe_out/KD" --k0 "$probe_out/K0/window.json" --k1a "$probe_out/K1a/window.json" --k1b "$probe_out/K1b/window.json" --k2 "$probe_out/K2/window.json" --dispatch "$probe_out/K2/run0/dispatch-measured.json" --input "$packet45/build/input"
# WS uses the full 128-token fixed suite with every-token oracle comparison.
# It retains early fixtures and does not need a separate speed-only companion.
"${probe_common[@]}" --window WS --mtp-k2-probe --output "$probe_out/WS" \
  --k0 "$probe_out/K0/window.json" --k1a "$probe_out/K1a/window.json" \
  --k1b "$probe_out/K1b/window.json" --k2 "$probe_out/K2/window.json" \
  --w0p "$probe_out/W0p/window.json" --kd "$probe_out/KD/window.json" \
  --dispatch "$probe_out/K2/run0/dispatch-measured.json" --suite-manifest "$probe_suite" \
  --controller native --repeat 1 --retain-steps 1-8
