#!/usr/bin/env bash
# A340 driver: three exact-2K rows with step + per-site all-reduce event timing on the promoted MTP0 line (control, real all-reduce).
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 340 19953 mtp0 3
