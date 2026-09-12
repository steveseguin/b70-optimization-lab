#!/usr/bin/env bash
# A362 driver: MTP1 promoted line on the gdn-roundstate v2 stage, step timing.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 362 19975 mtp1 3
