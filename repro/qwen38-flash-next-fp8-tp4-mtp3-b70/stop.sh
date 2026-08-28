#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\n' \
  'BLOCKED (pre-publication): this repro cannot launch a managed service, so it has' \
  'no verified PID/lock ownership contract and will not guess which process to stop.' >&2
exit 2
