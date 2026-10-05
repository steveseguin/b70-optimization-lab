#!/usr/bin/env bash
# Ends any single comparison trial that runs longer than a wall-time limit, so one thrashing trial cannot hold the
# cards for hours (2026-10-05: a prose-ledger trial wrote 926K tokens over 3.5 hours and delivered 6 of 20 batches).
# It ends the trial's own runner process by pid; the comparison script then records the trial as ended early and
# moves on. Run as a systemd user unit next to a comparison run:
#   systemd-run --user --unit ctx-trial-watchdog -E LIMIT_S=3600 .../trial-watchdog.sh <unit to watch>
# It exits when the watched unit is no longer active.
LIMIT_S=${LIMIT_S:-3600}
UNIT=${1:?unit to watch}
PATTERN='[h]arbor run'
while systemctl --user is-active -q "$UNIT"; do
  for pid in $(pgrep -f "$PATTERN"); do
    age=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ')
    if [ -n "$age" ] && [ "$age" -gt "$LIMIT_S" ]; then
      echo "$(date +%T) trial runner pid $pid has run ${age}s (limit ${LIMIT_S}s): ending it"
      ps -o args= -p "$pid" | cut -c1-200
      kill "$pid"
    fi
  done
  sleep 30
done
echo "$(date +%T) watched unit $UNIT is no longer active; watchdog exits"
