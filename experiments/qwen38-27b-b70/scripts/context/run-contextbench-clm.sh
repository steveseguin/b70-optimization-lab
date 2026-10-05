#!/usr/bin/env bash
# Zero-shot CLM agent (ClmAgent, unmodified) on kvstream tasks (or TASKS=<harbor task/dataset dir>).
#   API_BASE=http://127.0.0.1:8000/v1 run-contextbench-clm.sh /mnt/fast-ai/bench-results/context-<tag> [harbor args]
# All settings: see run-context-job.sh header.
exec "$(dirname "${BASH_SOURCE[0]}")/run-context-job.sh" clm "$@"
