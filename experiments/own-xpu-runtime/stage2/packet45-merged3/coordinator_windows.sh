#!/usr/bin/env bash
# Coordinator only, from repository root inside the admitted nice-0 systemd user unit.
set -euo pipefail
packet45=experiments/own-xpu-runtime/stage2/packet45-merged3
packet45_card=${1:?first card of adjacent pair required}
packet45_context=${2:?context 256,4096,32768 required}
packet45_draft_rank=${3:-0}
packet45_target_split=${6:-0}
# Split identity is bound into every prerequisite; byte admission remains in window.py.
case "$packet45_target_split" in 0|23|24) ;; *) echo "target split must be 0,23,24" >&2; exit 2;; esac
packet45_split_suffix=""
if [[ $packet45_target_split != 0 ]]; then packet45_split_suffix="-s$packet45_target_split"; fi
packet45_suite=${4:-experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json}
packet45_out="${5:-$packet45/build/c${packet45_context}-dr${packet45_draft_rank}${packet45_split_suffix}}"
packet45_input="$packet45/build/input"
packet45_oracle=experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective
packet45_diagnostic=()
if [[ ${PACKET45_DIAGNOSTIC_UNSEALED:-0} == 1 ]]; then packet45_diagnostic=(--diagnostic-unsealed); fi
packet45_k=(nice -n 19 ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet45/window.py" --authorized-device-window --card "$packet45_card" --context "$packet45_context" --draft-rank "$packet45_draft_rank" --target-split "$packet45_target_split" "${packet45_diagnostic[@]}")
packet45_w=(ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" python3 -B "$packet45/window.py" --authorized-device-window --card "$packet45_card" --context "$packet45_context" --draft-rank "$packet45_draft_rank" --target-split "$packet45_target_split" "${packet45_diagnostic[@]}")
"${packet45_k[@]}" --window K0 --output "$packet45_out/K0"
"${packet45_k[@]}" --window K1a --output "$packet45_out/K1a" --k0 "$packet45_out/K0/window.json" --dispatch "$packet45/dispatch-p45.json"
"${packet45_k[@]}" --window K1b --output "$packet45_out/K1b" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --dispatch "$packet45/dispatch-p45.json"
"${packet45_k[@]}" --window K2 --output "$packet45_out/K2" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --dispatch "$packet45/dispatch-p45.json" --seconds 14400
"${packet45_w[@]}" --window W0p --output "$packet45_out/W0p" --k0 "$packet45_out/K0/window.json"
"${packet45_k[@]}" --window KD --output "$packet45_out/KD" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --input "$packet45_input"
"${packet45_w[@]}" --window W2m --output "$packet45_out/W2m" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --w0p "$packet45_out/W0p/window.json" --kd "$packet45_out/KD/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --input "$packet45_input" --oracle "$packet45_oracle" --controller native --retain-steps 1-8
"${packet45_w[@]}" --window WS --output "$packet45_out/WS" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --w0p "$packet45_out/W0p/window.json" --kd "$packet45_out/KD/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet45_suite" --controller native --repeat 1 --retain-steps 1-8
"${packet45_w[@]}" --window WSs --output "$packet45_out/WSs" --k0 "$packet45_out/K0/window.json" --k1a "$packet45_out/K1a/window.json" --k1b "$packet45_out/K1b/window.json" --k2 "$packet45_out/K2/window.json" --w0p "$packet45_out/W0p/window.json" --dispatch "$packet45_out/K2/run0/dispatch-measured.json" --suite-manifest "$packet45_suite" --controller native --repeat 1 --retain-steps 1-8
