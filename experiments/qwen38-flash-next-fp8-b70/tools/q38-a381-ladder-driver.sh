#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-depth-ladder-driver.sh" 381 19994 mtp0 33280 2 2048,8192,16384,32768
