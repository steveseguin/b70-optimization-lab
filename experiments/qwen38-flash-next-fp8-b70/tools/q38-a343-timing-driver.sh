#!/usr/bin/env bash
# A343 driver: three exact-2K rows with step timing on the promoted MTP1 line (fused QSA, three exact-verify selectors).
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 343 19956 mtp1 3
