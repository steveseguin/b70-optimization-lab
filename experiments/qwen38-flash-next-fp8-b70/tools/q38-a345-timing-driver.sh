#!/usr/bin/env bash
# A345 driver: MTP1 promoted line, step timing, skip=moe_gemm
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 345 19958 mtp1 3
