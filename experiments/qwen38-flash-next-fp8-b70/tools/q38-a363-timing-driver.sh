#!/usr/bin/env bash
# A363 driver: MTP1 promoted line on the gdn-roundstate v2 stage, step timing.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 363 19976 mtp1 3
