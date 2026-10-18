#!/bin/bash
# Proposed coordinator launcher. No action without explicit --launch.
set -euo pipefail
if [[ $# != 4 ]]; then
  echo 'usage: launch-proposed.sh bracket|record --plan|--launch REVIEWED_UTC LD_LIBRARY_PATH' >&2
  exit 2
fi
mode=$1; action=$2; reviewed=$3; libraries=$4
case "$mode" in bracket|record) ;; *) exit 2 ;; esac
case "$action" in --plan|--launch) ;; *) exit 2 ;; esac
packet_dir=$(cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(cd -- "$packet_dir/../../../.." && pwd)
output_dir="$packet_dir/evidence/card0-58j-$mode-a"
args=("$mode" --output-root "$output_dir" --faults-reviewed-through "$reviewed")
if [[ $mode == record ]]; then args+=(--bracket-root "$packet_dir/evidence/card0-58j-bracket-a"); fi
cd -- "$repo_dir"
if [[ $action == --plan ]]; then
  exec nice -n 19 taskset -c 8-15,24-31 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$libraries" \
    /usr/bin/python3 -B "$packet_dir/campaign.py" "${args[@]}" --plan < /dev/null
fi
# Coordinator invokes only after the two-card record chain has drained.
# Per-window admission also holds B, validates all cards are empty, and checks RAM.
exec systemd-run --user --unit="packet58-j-$mode-a" \
  --property=Nice=0 --property=CPUAffinity='0-3 16-19' \
  --property=KillSignal=SIGTERM --property=KillMode=control-group \
  --property=SendSIGKILL=no --property=TimeoutStopSec=infinity \
  --property=StandardInput=null --working-directory="$repo_dir" \
  /usr/bin/env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$libraries" \
  /usr/bin/python3 -B "$packet_dir/campaign.py" "${args[@]}" --authorized-device-window < /dev/null
