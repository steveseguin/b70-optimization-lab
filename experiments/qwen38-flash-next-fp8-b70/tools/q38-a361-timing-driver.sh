#!/usr/bin/env bash
# A361 driver: MTP1 promoted line on the gdn-roundstate v2 stage, step timing.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 361 19974 mtp1 3
