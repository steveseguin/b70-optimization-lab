#!/usr/bin/env bash
# Preparation does not authorize execution. Admission is enforced in Python.
set -euo pipefail
driver_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec nice -n 19 env OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/python3 -B "$driver_dir/window_driver.py" "$@"
