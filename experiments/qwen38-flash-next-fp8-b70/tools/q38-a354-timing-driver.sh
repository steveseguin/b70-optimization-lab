#!/usr/bin/env bash
# A354 driver: MTP1 promoted line, step timing, skip=hc_mix (zero-injection fix)
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 354 19967 mtp1 3
