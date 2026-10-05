#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper: the core subset of the second comparison against the server serve_run started.
cd "$(dirname "$0")" && SUBSET=${SUBSET:-core} exec ./second-comparison.sh
