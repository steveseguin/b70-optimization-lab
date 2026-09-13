#!/usr/bin/env bash
# A379 driver: exact-mode line, step timing, one row-wise selector off (timing only).
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 379 19992 mtp1 3
