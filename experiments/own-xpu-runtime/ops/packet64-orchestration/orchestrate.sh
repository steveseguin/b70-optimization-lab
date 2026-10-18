#!/usr/bin/env bash
set -Eeuo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# Python owns durable step/exit logging; this catches interpreter/exec failures.
trap 'rc=$?; printf "%s shell EXIT rc=%s\n" "$(date -u +%FT%TZ)" "$rc" >> "$HERE/orchestrate.log"' EXIT
exec nice -n 19 taskset -c 8-15,24-31 python3 -B "$HERE/orchestrate.py" "$@"
