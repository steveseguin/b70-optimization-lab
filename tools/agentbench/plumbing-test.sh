#!/usr/bin/env bash
# plumbing-test.sh AGENT [SLOT]: the CPU-only wiring test of one agent (no model, no GPU).
#
#   fake_agent_server.py (127.0.0.1:183xx)  <-  ctxkeeper --recipe agent (127.0.0.1:183yy)  <-  bridge  <-  agent
#
# Runs the agent on repair-n40-s2x through the normal runner (TAP=full, so every request the agent sends is kept),
# then plumbing_check.py checks: requests reach the proxy as Chat Completions with tools; the scripted `next` ran in
# /app and the ticket text came back to the model; the agent ended by itself when told the job was done; the verifier
# wrote details.json; every request carried the whole history. SLOT (0-9) picks the ports: fake 18310+SLOT, keeper
# 18320+SLOT. Results: $PLUMB_ROOT/AGENT/ (default /mnt/fast-ai/bench-results/agentbench-plumbing-20261014).
#
# MODE=stress: the history test. The fake makes the agent run BIG_STEPS commands (default 170) that each print
# BIG_CHARS (default 24000) characters of random text, so its history passes 4M characters (over 1M tokens by any
# count). A history that stops growing, or a request that no longer starts with the one before, is the agent's own
# compaction. Also measures the agent's memory at that history size, and that ctxkeeper cut without a restart.
# Results go to $PLUMB_ROOT/AGENT-stress/; the tap keeps summaries only.
#
# MODE=slow: the basic test, but the fake model takes DELAY_S (default 330) seconds over its second reply, sending
# nothing meanwhile, as a long reply behind ctxkeeper does (the proxy answers in one piece at the end). Passes if the
# agent waits without a retry or an error. Results: $PLUMB_ROOT/AGENT-slow/.
set -uo pipefail
AGENT=${1:?usage: plumbing-test.sh AGENT [SLOT]}
SLOT=${2:-0}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TASK=${TASK:-/mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2/tasks/repair-n40-s2x}
ROOT=${PLUMB_ROOT:-/mnt/fast-ai/bench-results/agentbench-plumbing-20261014}
CTXKEEPER=${CTXKEEPER:-/mnt/fast-ai/venvs/ctxkeeper-1.0.0/bin/ctxkeeper}
FP=$((18310 + SLOT)); KP=$((18320 + SLOT))
MODE=${MODE:-basic}
TAG=${RUN_TAG:+-$RUN_TAG}          # RUN_TAG=x keeps this run apart: results in AGENT[-MODE]-x/
W="$ROOT/$AGENT$TAG"; TAPMODE=full; LIMIT=${TIME_LIMIT:-300}
if [ "$MODE" = slow ]; then
  W="$ROOT/$AGENT-slow$TAG"; LIMIT=${TIME_LIMIT:-900}
  export FAKE_DELAY_S=${DELAY_S:-330}
fi
if [ "$MODE" = stress ]; then
  W="$ROOT/$AGENT-stress$TAG"; TAPMODE=summary; LIMIT=${TIME_LIMIT:-2400}
  export FAKE_BIG_STEPS=${BIG_STEPS:-170} FAKE_BIG_CHARS=${BIG_CHARS:-24000}
fi
rm -rf "$W"; mkdir -p "$W"
python3 -I "$HERE/fake_agent_server.py" "$FP" --log "$W/fake-requests.jsonl" > "$W/fake.out" 2> "$W/fake.err" &
FAKE=$!
"$CTXKEEPER" --upstream "http://127.0.0.1:$FP" --recipe agent --port "$KP" --state-dir "$W/ctxkeeper-state" \
  > "$W/ctxkeeper.out" 2> "$W/ctxkeeper.err" &
KEEPER=$!
trap 'kill $FAKE $KEEPER 2>/dev/null' EXIT
for _ in $(seq 50); do curl -s -m 1 "http://127.0.0.1:$KP/v1/models" >/dev/null 2>&1 && break; sleep 0.2; done
TAP=$TAPMODE AGENT_MEM=${AGENT_MEM:-2g} "$HERE/run-agent-job.sh" "$AGENT" "$TASK" "$W/out" "plumb-$AGENT-$MODE" \
  "http://127.0.0.1:$KP/v1" "$LIMIT" 2>&1 | tee "$W/runner.log"
curl -s -m 5 "http://127.0.0.1:$KP/ctxkeeper/status" > "$W/ctxkeeper-status.json"
python3 -I "$HERE/plumbing_check.py" "$W" "$MODE" | tee "$W/plumbing-result.json"
