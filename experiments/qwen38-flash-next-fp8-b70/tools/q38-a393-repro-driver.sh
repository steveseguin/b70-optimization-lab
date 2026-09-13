#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-repro-driver.sh" 393 20010 mtp0 4352
