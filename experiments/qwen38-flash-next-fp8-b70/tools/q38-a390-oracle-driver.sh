#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-concurrency-oracle-driver.sh" 390 20007 mtp0 4352 1,2,4,8
