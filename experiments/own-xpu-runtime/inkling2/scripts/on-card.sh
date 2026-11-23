#!/bin/bash
# on-card.sh <card> <command ...>: run one Inkling-2 job on one card, holding that card's lock for its whole run.
# Cards 1-5 by default (card 0 drives the desktop); a second job for a busy card fails at once instead of sharing it.
# Refuses to start while the DeepSeek server claims the cards (six.active) or host memory is short.
set -u
card=$1; shift
LOCKS=${INK_LOCKS:-/home/steve/inkling-work/locks}
mkdir -p "$LOCKS"
[ -e /home/steve/dsv41-work/six.active ] && { echo "on-card: the cards are claimed ($(cat /home/steve/dsv41-work/six.active)); not starting"; exit 3; }
avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
[ "$avail" -ge "${INK_MIN_MIB:-2500}" ] || { echo "on-card: only $avail MiB host memory available; not starting"; exit 3; }
exec 9> "$LOCKS/card$card.lock"
flock -n 9 || { echo "on-card: card $card is busy"; exit 4; }
echo "$$ $(date +%FT%T) $*" > "$LOCKS/card$card.owner"
set +u # setvars.sh reads unset variables
source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
set -u
export ZES_ENABLE_SYSMAN=1 INK_CARD=$card
"$@"
rc=$?
rm -f "$LOCKS/card$card.owner"
exit $rc
