#!/bin/bash
# on-card.sh <card> <command ...>: run one Inkling-2 job on one card, holding that card's lock for its whole run.
# Cards 1-5 by default (card 0 drives the desktop); a second job for a busy card fails at once instead of sharing it.
# Refuses to start while the DeepSeek server claims the cards (six.active) or host memory is short.
set -u
card=${1:-}; shift
# a card number 1-5 (an empty argument would lock "card.lock" and run on card 0, which drives the desktop)
case "$card" in [1-9]) ;; 0) [ "${INK_ALLOW_CARD0:-0}" = 1 ] || { echo "on-card: card 0 drives the desktop (INK_ALLOW_CARD0=1 to use it)"; exit 2; } ;;
  *) echo "on-card: '$card' is not a card number"; exit 2 ;; esac
LOCKS=${INK_LOCKS:-/home/steve/inkling-work/locks}
mkdir -p "$LOCKS"
[ -e /home/steve/dsv41-work/six.active ] && { echo "on-card: the cards are claimed ($(cat /home/steve/dsv41-work/six.active)); not starting"; exit 3; }
avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
[ "$avail" -ge "${INK_MIN_MIB:-2500}" ] || { echo "on-card: only $avail MiB host memory available; not starting"; exit 3; }
exec 9> "$LOCKS/card$card.lock"
flock -n 9 || { echo "on-card: card $card is busy"; exit 4; }
echo "$$ $(date +%FT%T) $*" > "$LOCKS/card$card.owner"
# a split engine (INK_SPLIT_CARDS / INK_SPLIT_CARD: the cards of the parts before this card's) holds those cards too
owned="$card"
for c in $([ -n "${INK_SPLIT:-}" ] && echo "${INK_SPLIT_CARDS:-${INK_SPLIT_CARD:-}}" | tr ',' ' '); do
  case " $owned " in *" $c "*) continue ;; esac
  case "$c" in [1-9]) ;; 0) [ "${INK_ALLOW_CARD0:-0}" = 1 ] || { echo "on-card: card 0 drives the desktop"; rm -f "$LOCKS/card$card.owner"; exit 2; } ;;
    *) echo "on-card: split card '$c' is not a card number"; rm -f "$LOCKS/card$card.owner"; exit 2 ;; esac
  exec {fd}> "$LOCKS/card$c.lock"
  flock -n $fd || { echo "on-card: card $c is busy"; for o in $owned; do rm -f "$LOCKS/card$o.owner"; done; exit 4; }
  echo "$$ $(date +%FT%T) (split part) $*" > "$LOCKS/card$c.owner"
  owned="$owned $c"
done
set +u # setvars.sh reads unset variables
source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
set -u
export ZES_ENABLE_SYSMAN=1 INK_CARD=$card
"$@"
rc=$?
for o in $owned; do rm -f "$LOCKS/card$o.owner"; done
exit $rc
