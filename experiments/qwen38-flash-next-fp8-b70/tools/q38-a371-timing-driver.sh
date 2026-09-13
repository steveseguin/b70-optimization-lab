#!/usr/bin/env bash
# A371 driver: MTP1 exact-serial-GDN line (stage v2), step timing, skip=gdn_attn.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 371 19984 mtp1 3
