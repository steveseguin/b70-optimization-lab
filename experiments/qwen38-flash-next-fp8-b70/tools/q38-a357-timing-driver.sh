#!/usr/bin/env bash
# A357 driver: MTP1 promoted line + serial-GDN diagnostics, step timing.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 357 19970 mtp1 3
