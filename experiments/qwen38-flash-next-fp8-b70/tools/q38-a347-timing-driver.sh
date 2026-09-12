#!/usr/bin/env bash
# A347 driver: MTP1 promoted line, step timing, skip=qsa_attn
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-timing-driver.sh" 347 19960 mtp1 3
