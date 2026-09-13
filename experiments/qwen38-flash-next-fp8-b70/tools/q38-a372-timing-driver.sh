#!/usr/bin/env bash
# A372 driver: MTP1 exact-serial-GDN line (stage v2), step timing, skip=qsa_attn.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 372 19985 mtp1 3
