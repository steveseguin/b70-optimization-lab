#!/usr/bin/env bash
# A351 driver: MTP0 promoted line, step timing, skip=qsa_attn
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 351 19964 mtp0 3
