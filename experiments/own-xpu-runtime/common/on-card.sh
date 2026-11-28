#!/bin/bash
# on-card.sh <card> <command ...>: generic per-card lock + host-RAM guard + oneAPI wrapper for B70 lanes.
# Env overrides:
#   B70_LOCKS       lock directory (default /tmp/b70-card-locks)
#   B70_MIN_MIB     minimum MemAvailable MiB to launch (default 2500)
#   B70_CLAIM_FILE  optional exclusive cluster-claim file to respect (default unset)
#   B70_EXTRA_CARDS optional comma-separated extra cards to lock for multi-card split runs
set -u
card=${1:-}; shift || true
case "$card" in [0-9]) ;; *) echo "on-card: '$card' is not a valid card number (0-9)"; exit 2 ;; esac
[ "$#" -gt 0 ] || { echo "on-card: missing command"; exit 2; }

LOCKS=${B70_LOCKS:-/tmp/b70-card-locks}
mkdir -p "$LOCKS"

if [ -n "${B70_CLAIM_FILE:-}" ] && [ -e "$B70_CLAIM_FILE" ]; then
    echo "on-card: cards claimed by $B70_CLAIM_FILE ($(cat "$B70_CLAIM_FILE")); not starting"
    exit 3
fi

avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
[ "$avail" -ge "${B70_MIN_MIB:-2500}" ] || { echo "on-card: only $avail MiB host memory available (need ${B70_MIN_MIB:-2500})"; exit 3; }

exec 9> "$LOCKS/card$card.lock"
flock -n 9 || { echo "on-card: card $card is busy"; exit 4; }
echo "$$ $(date +%FT%T) $*" > "$LOCKS/card$card.owner"
owned="$card"

for c in $(echo "${B70_EXTRA_CARDS:-}" | tr ',' ' '); do
    case " $owned " in *" $c "*) continue ;; esac
    case "$c" in [0-9]) ;; *) echo "on-card: invalid extra card '$c'"; rm -f "$LOCKS/card$card.owner"; exit 2 ;; esac
    exec {fd}> "$LOCKS/card$c.lock"
    flock -n "$fd" || { echo "on-card: card $c is busy"; for o in $owned; do rm -f "$LOCKS/card$o.owner"; done; exit 4; }
    echo "$$ $(date +%FT%T) (extra) $*" > "$LOCKS/card$c.owner"
    owned="$owned $c"
done

set +u
[ -f /opt/intel/oneapi/setvars.sh ] && source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1
set -u
export ZES_ENABLE_SYSMAN=1
"$@"
rc=$?
for o in $owned; do rm -f "$LOCKS/card$o.owner"; done
exit $rc
