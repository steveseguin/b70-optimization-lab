#!/usr/bin/env bash
# A349 driver: MTP0 promoted line, step timing, skip=moe_gemm
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 349 19962 mtp0 3
