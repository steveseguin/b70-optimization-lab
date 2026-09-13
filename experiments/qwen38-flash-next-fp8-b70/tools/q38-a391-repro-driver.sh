#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-repro-driver.sh" 391 20008 mtp0 4352
