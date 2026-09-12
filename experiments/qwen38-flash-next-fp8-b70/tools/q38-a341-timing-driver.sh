#!/usr/bin/env bash
# A341 driver: as A340 with the MoE final all-reduce on a static zero buffer (Q38_DIAG_SKIP=moe_allreduce_zero_input); timing only.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 341 19954 mtp0 3
