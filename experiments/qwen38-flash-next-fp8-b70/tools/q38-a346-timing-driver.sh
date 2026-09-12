#!/usr/bin/env bash
# A346 driver: MTP1 promoted line, step timing, skip=gdn_attn
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 346 19959 mtp1 3
