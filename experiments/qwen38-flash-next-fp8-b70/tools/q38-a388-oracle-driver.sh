#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/q38-concurrency-oracle-driver.sh" 388 20005 mtp0 4352 1,2,4,8
