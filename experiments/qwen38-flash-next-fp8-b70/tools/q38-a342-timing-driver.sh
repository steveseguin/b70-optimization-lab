#!/usr/bin/env bash
# A342 driver: as A340 with the MoE final all-reduce skipped entirely (Q38_DIAG_SKIP=moe_allreduce); timing only.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 342 19955 mtp0 3
