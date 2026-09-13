#!/usr/bin/env bash
# A370 driver: MTP1 exact-serial-GDN line (stage v2), step timing, skip=moe_gemm.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 386 20003 mtp1 3
