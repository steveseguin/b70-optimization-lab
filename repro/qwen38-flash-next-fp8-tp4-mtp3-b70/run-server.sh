#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\n' \
  'BLOCKED (pre-publication): this foundation is not a runnable service recipe.' \
  'Use the historical experiment launcher only to inspect the measured identity;' \
  'do not treat it as a portable launch path.' >&2
exit 2
