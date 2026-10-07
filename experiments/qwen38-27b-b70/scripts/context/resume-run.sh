#!/usr/bin/env bash
# MU_RUN_SCRIPT wrapper that can be restarted: every block writes into CLIENT_TOP (fixed across restarts), so
# finished trials are skipped and only the missing ones run. Blocks come from a plan file (one `run` line each).
#   CLIENT_TOP=/mnt/fast-ai/bench-results/context-plan-A PLAN=/path/plan.sh
cd "$(dirname "$0")" || exit 2
TOP=${CLIENT_TOP:?set CLIENT_TOP}; mkdir -p "$TOP"
run() { sub=$1; shift; [ -e "$TOP/STOP" ] && { echo "stopped by STOP file"; exit 0; }; echo "### [$sub] $*"; mkdir -p "$TOP/$sub"
        [ -e "$TOP/STOP" ] && touch "$TOP/$sub/STOP"; env "$@" OUT_DIR="$TOP/$sub" SUBSET=core ./second-comparison.sh || echo "### block ended rc=$?"
        curl -sf -m 10 "$BASE_URL/health" >/dev/null || { echo "### server gone; leaving the rest for a restart"; exit 3; }; }
export READ_REASONS=0
# shellcheck disable=SC1090
source "${PLAN:?set PLAN}"
echo "### plan complete"
