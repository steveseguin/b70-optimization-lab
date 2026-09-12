#!/usr/bin/env bash
# A360 driver: MTP1 promoted line on the gdn-roundstate stage, step timing.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 360 19973 mtp1 3
