#!/usr/bin/env bash
# A373 driver: MTP1 exact-serial-GDN line (stage v2), step timing, skip=hc_mix.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 373 19986 mtp1 3
