#!/usr/bin/env bash
# A352 driver: MTP0 promoted line, step timing, skip=hc_mix
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 352 19965 mtp0 3
