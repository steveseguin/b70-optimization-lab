#!/usr/bin/env bash
# Launch one run_phase.sh phase as a transient user unit holding the card locks it needs (bounded 30-minute wait per lock).
# Copy of research/two-card-flags-2026-10-31/launch_phase.sh for research/aot-tp-2026-10-31: both binaries (SO_BIN_JIT,
# SO_BIN_AOT) and the cards to lock as LOCKS (card numbers, default the card of TC_BDF; the four-card TP phase takes
# LOCKS="23 27 47": rank 1 on 23+47, rank 0 on 23+27). Restart=no, KillMode=process, LimitNOFILE=1048576.
# Usage: LOCKS="..." TC_BDF=... launch_phase.sh JIT_BINARY AOT_BINARY PHASE ARM...
set -eu
D=$(cd "$(dirname "$0")" && pwd)
JIT=$1; AOT=$2; PHASE=$3; shift 3
BDF=${TC_BDF:-0000:43:00.0}
LOCKS=${LOCKS:-${BDF:5:2}}
cmd=()
for c in $LOCKS; do [ -e "/dev/shm/card$c.lock" ] || { echo "no lock file for card $c"; exit 2; }; cmd+=(flock -w 1800 -E 75 "/dev/shm/card$c.lock"); done
systemd-run --user --unit="aot-tp-$PHASE" --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
  -E SO_BIN_JIT="$JIT" -E SO_BIN_AOT="$AOT" -E TC_BDF="$BDF" "${cmd[@]}" taskset -c 0-3,16-19 bash "$D/run_phase.sh" "$PHASE" "$@"
