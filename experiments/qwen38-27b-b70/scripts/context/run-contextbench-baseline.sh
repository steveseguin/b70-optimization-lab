#!/usr/bin/env bash
# Baselines on the same tasks.  BASELINE=summary (Codex-style harness summary, default) | plain (no management) | both
#   API_BASE=http://127.0.0.1:8000/v1 BASELINE=both run-contextbench-baseline.sh /mnt/fast-ai/bench-results/context-<tag> [harbor args]
# All settings: see run-context-job.sh header.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
case "${BASELINE:-summary}" in
  both) "$HERE/run-context-job.sh" summary "$@"; JOB_NAME= exec "$HERE/run-context-job.sh" plain "$@" ;;
  summary|plain) exec "$HERE/run-context-job.sh" "${BASELINE:-summary}" "$@" ;;
  *) echo "BASELINE must be summary|plain|both" >&2; exit 2 ;;
esac
