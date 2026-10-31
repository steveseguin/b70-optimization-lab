#!/usr/bin/env bash
# Launch one run_phase.sh phase as a transient user unit holding the card locks it needs (bounded 30-minute waits).
# Usage: launch_phase.sh BINARY LOCKSET PHASE ARM...   LOCKSET: one (card43) | four (cards 23, 27, 47; the rank harness's TP
# pairs are 23+27 and 23+47) | all (23, 27, 43, 47). Restart=no, KillMode=process, LimitNOFILE=1048576.
set -eu
D=$(cd "$(dirname "$0")" && pwd)
BIN=$1; SET=$2; PHASE=$3; shift 3
case "$SET" in
  one) cards=(43) ;; four) cards=(23 27 47) ;; all) cards=(23 27 43 47) ;; *) echo "lockset?"; exit 2 ;;
esac
locks=(); for c in "${cards[@]}"; do locks+=(flock -w 1800 -E 75 /dev/shm/card$c.lock); done
systemd-run --user --unit="xtail-$PHASE" --collect -p Restart=no -p KillMode=process -p LimitNOFILE=1048576 \
  -E SO_BIN="$BIN" "${locks[@]}" taskset -c 0-3,16-19 bash "$D/run_phase.sh" "$PHASE" "$@"
