#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 5 ]; then
  echo 'usage: coordinator-timing.sh RUNTIME_LIBRARY_PATH REVIEWED_THROUGH_UTC NEW_OUTPUT_DIRECTORY EXACT1_WINDOW_JSON EXACT2_WINDOW_JSON' >&2
  exit 2
fi
packet48_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/nice -n 19 /usr/bin/taskset -c 4-15,20-31 \
  /usr/bin/env -i LD_LIBRARY_PATH="$1" \
  /usr/bin/python3 -B "$packet48_dir/window.py" \
  --authorized-device-window --card 0 --mode timing \
  --faults-reviewed-through "$2" --output "$3" --exactness "$4" "$5"
