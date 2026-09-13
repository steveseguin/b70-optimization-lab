#!/usr/bin/env bash
# A369 driver: MTP1 exact-serial-GDN line (stage v2), step timing, skip=none.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 369 19982 mtp1 3
