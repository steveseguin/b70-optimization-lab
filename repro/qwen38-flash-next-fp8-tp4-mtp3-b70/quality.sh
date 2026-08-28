#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\n' \
  'BLOCKED (pre-publication): no package replay exists for this extracted runtime.' \
  'Quality qualification must follow a successful exact-identity startup and may not' \
  'inherit the historical result without a new artifact-only replay.' >&2
exit 2
