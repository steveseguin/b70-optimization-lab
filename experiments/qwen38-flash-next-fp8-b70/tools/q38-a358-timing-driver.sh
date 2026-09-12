#!/usr/bin/env bash
# A358 driver: MTP1 promoted line + serial-GDN diagnostics, step timing.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 358 19971 mtp1 3
