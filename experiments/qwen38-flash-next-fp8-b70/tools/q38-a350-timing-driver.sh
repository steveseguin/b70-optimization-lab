#!/usr/bin/env bash
# A350 driver: MTP0 promoted line, step timing, skip=gdn_attn
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 350 19963 mtp0 3
