#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 4 ]; then
  echo 'usage: coordinator.sh RUNTIME_LIBRARY_PATH REVIEWED_THROUGH_UTC CARD_2_OR_3 NEW_OUTPUT_DIRECTORY' >&2
  exit 2
fi
packet55_h2d_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/nice -n 19 /usr/bin/taskset -c 4-15,20-31 \
  /usr/bin/env -i LD_LIBRARY_PATH="$1" \
  /usr/bin/python3 -B "$packet55_h2d_dir/window.py" \
  --authorized-device-window --card "$3" --faults-reviewed-through "$2" --output "$4"
