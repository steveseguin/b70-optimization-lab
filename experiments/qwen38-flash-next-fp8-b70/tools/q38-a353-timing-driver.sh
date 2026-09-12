#!/usr/bin/env bash
# A353 driver: MTP0 promoted line, step timing, skip=hc_mix (zero-injection fix)
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 353 19966 mtp0 3
