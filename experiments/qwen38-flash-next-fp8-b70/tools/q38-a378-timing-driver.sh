#!/usr/bin/env bash
# A378 driver: exact-mode line, step timing, one row-wise selector off (timing only).
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 378 19991 mtp1 3
