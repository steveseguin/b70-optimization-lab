#!/usr/bin/env bash
# Coordinator only: execute in a nice-0 systemd unit. Never run by CPU preparation.
set -euo pipefail
packet44=experiments/own-xpu-runtime/stage2/packet44-context
if [ "$#" -ne 2 ]; then
  echo "Usage: bash coordinator_windows.sh FIRST_CARD CONTEXT (4096 or 32768)" >&2
  exit 2
fi
packet44_card="$1"
packet44_context="$2"
case "$packet44_context" in 4096|32768) ;; *) exit 2 ;; esac
case "$packet44_card" in 0|1|2) ;; *) exit 2 ;; esac
packet44_out="$packet44/build/c$packet44_context"
packet44_input="$packet44/build/input"
packet44_oracle=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
packet44_suite=experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json
# Alternative: experiments/own-xpu-runtime/stage2/suite-inputs-20261012/suite-manifest.json
packet44_k=(nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet44/window.py" --authorized-device-window --card "$packet44_card" --context "$packet44_context")
packet44_w=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet44/window.py" --authorized-device-window --card "$packet44_card" --context "$packet44_context")
"${packet44_k[@]}" --window K0 --output "$packet44_out/K0"
"${packet44_k[@]}" --window K1a --output "$packet44_out/K1a" --k0 "$packet44_out/K0/window.json" --dispatch "$packet44/dispatch-p38.json"
"${packet44_k[@]}" --window K1b --output "$packet44_out/K1b" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --dispatch "$packet44/dispatch-p38.json"
"${packet44_k[@]}" --window K2 --output "$packet44_out/K2" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --dispatch "$packet44/dispatch-p38.json" --seconds 10800
"${packet44_w[@]}" --window W0p --output "$packet44_out/W0p" --k0 "$packet44_out/K0/window.json"
"${packet44_k[@]}" --window KD --output "$packet44_out/KD" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --input "$packet44_input"
"${packet44_w[@]}" --window W2m --output "$packet44_out/W2m" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --w0p "$packet44_out/W0p/window.json" --kd "$packet44_out/KD/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --input "$packet44_input" --oracle "$packet44_oracle" --controller native
"${packet44_w[@]}" --window WS --output "$packet44_out/WS" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --w0p "$packet44_out/W0p/window.json" --kd "$packet44_out/KD/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet44_suite" --controller native --repeat 2
"${packet44_w[@]}" --window WSs --output "$packet44_out/WSs" --k0 "$packet44_out/K0/window.json" --k1a "$packet44_out/K1a/window.json" --k1b "$packet44_out/K1b/window.json" --k2 "$packet44_out/K2/window.json" --w0p "$packet44_out/W0p/window.json" --dispatch "$packet44_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet44_suite" --controller native --repeat 2
