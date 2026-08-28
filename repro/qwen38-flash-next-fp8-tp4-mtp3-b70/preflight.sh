#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\n' \
  'BLOCKED (research-status): deployment preflight is intentionally unavailable.' \
  'Closed: public runtime URLs/readback and exact model/source/runtime identity.' \
  'Observed only: Python/runtime versions; no complete hash-addressed binary wheelhouse.' \
  'Missing closure: portable four-B70 topology checks and artifact-only origin-host replay.' >&2
exit 2
