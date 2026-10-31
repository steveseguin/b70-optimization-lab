#!/usr/bin/env bash
# Launch one run_phase.sh phase as a transient user unit holding the card lock it needs (bounded 30-minute wait).
# Copy of research/tp/hc-split-2026-10-30/launch_phase.sh for research/two-card-flags-2026-10-31: one card only, the card
# of TC_BDF (default 0000:47:00.0, lock /dev/shm/card47.lock). Restart=no, KillMode=process, LimitNOFILE=1048576.
# Usage: launch_phase.sh BINARY PHASE ARM...
set -eu
D=$(cd "$(dirname "$0")" && pwd)
BIN=$1; PHASE=$2; shift 2
BDF=${TC_BDF:-0000:47:00.0}; c=${BDF:5:2}
[ -e "/dev/shm/card$c.lock" ] || { echo "no lock file for $BDF"; exit 2; }
systemd-run --user --unit="twocard-$PHASE" --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
  -E SO_BIN="$BIN" -E TC_BDF="$BDF" flock -w 1800 -E 75 "/dev/shm/card$c.lock" taskset -c 0-3,16-19 bash "$D/run_phase.sh" "$PHASE" "$@"
