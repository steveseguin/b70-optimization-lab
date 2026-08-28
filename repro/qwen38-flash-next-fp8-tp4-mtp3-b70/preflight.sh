#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\n' \
  'BLOCKED (pre-publication): deployment preflight is intentionally unavailable.' \
  'Missing closure: public runtime URLs/readback, an exact installable dependency lock,' \
  'portable four-B70 topology checks, and an artifact-only origin-host replay.' >&2
exit 2
