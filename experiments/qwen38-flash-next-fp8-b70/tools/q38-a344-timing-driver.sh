#!/usr/bin/env bash
# A344 driver: MTP1 promoted line, step timing, skip=none
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 344 19957 mtp1 3
