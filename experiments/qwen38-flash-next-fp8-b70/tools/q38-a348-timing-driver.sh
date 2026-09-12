#!/usr/bin/env bash
# A348 driver: MTP1 promoted line, step timing, skip=hc_mix
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 348 19961 mtp1 3
