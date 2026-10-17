#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec nice -n 19 taskset -c 4-15,20-31 python3 -B "$here/run_driver.py" "$@"
