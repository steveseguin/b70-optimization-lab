#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-concurrency-oracle-driver.sh" 377 19990 mtp0 4352 1,2,4,8
