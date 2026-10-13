#!/usr/bin/env bash
# Coordinator-only entrypoint. Does not bypass any packet44 admission guard.
set -euo pipefail
recipe=repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70
packet=experiments/own-xpu-runtime/stage2/packet44-context
mode=${1:?benchmark, launch or stop}; shift
: "${UNIT:?set a unique ownrt-p44-... systemd user unit name}"
[[ "$UNIT" =~ ^ownrt-p44-[a-zA-Z0-9_-]+$ ]] || exit 2
if [[ "$mode" == stop ]]; then
  # Signal only the supervising wrapper; it owns the cooperative rank stop pipe.
  exec systemctl --user kill --kill-who=main --signal=SIGTERM "$UNIT.service"
fi
[[ ${1:-} == --authorized-device-window && $# == 1 ]] || { echo "Coordinator authorization flag required" >&2; exit 2; }
[[ "$mode" == benchmark || "$mode" == launch ]] || exit 2
: "${CHAIN_DIR:?set the fresh same-boot K0/K1a/K1b/K2/W0p/KD chain directory}"
: "${OUT_DIR:?set a new output directory beneath packet44/build}"
: "${CARD:?set first card of adjacent pair (0, 1 or 2)}"
: "${LD_LIBRARY_PATH:?provide the qualified existing library path}"
context=${CONTEXT:-4096}
[[ "$context" == 4096 || "$context" == 32768 ]] || exit 2
[[ "$CARD" =~ ^[012]$ ]] || exit 2
# W windows require a nice-0 coordinator parent; do not silently raise priority.
[[ $(ps -o ni= -p $$ | tr -d " ") == 0 ]] || { echo "W windows require a coordinator nice-0 parent; see WINDOW.md" >&2; exit 2; }
args=(--authorized-device-window --card "$CARD" --context "$context" --output "$OUT_DIR"
 --k0 "$CHAIN_DIR/K0/window.json" --k1a "$CHAIN_DIR/K1a/window.json"
 --k1b "$CHAIN_DIR/K1b/window.json" --k2 "$CHAIN_DIR/K2/window.json"
 --w0p "$CHAIN_DIR/W0p/window.json" --kd "$CHAIN_DIR/KD/window.json"
 --dispatch "$CHAIN_DIR/K2/run0/dispatch-measured.json" --controller native)
if [[ "$mode" == benchmark ]]; then
  args+=(--window WS --suite-manifest experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json --repeat 1)
  wait_args=(--wait)
else
  args+=(--window W2m --input "$packet/build/input" --oracle experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective)
  wait_args=()
fi
systemd-run --user --unit="$UNIT" --collect "${wait_args[@]}" \
 --property=WorkingDirectory="$PWD" --property=Restart=no --property=KillMode=process \
 --property=SendSIGKILL=no --property=TimeoutStopSec=infinity \
 --property=CPUAffinity="$(python3 -B -c 'import os; print(" ".join(map(str, sorted(os.sched_getaffinity(0)))))')" \
 ionice -c 3 env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
 python3 -B "$PWD/$packet/window.py" "${args[@]}"
if [[ "$mode" == benchmark ]]; then
  nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$recipe/scripts/verify.py" --suite-dir "$OUT_DIR/run"
fi
