#!/usr/bin/env bash
# Emit only genuinely new campaign events.
#
# `tail -F` follows a path, so archiving a log (which this campaign does on every failure) makes it
# reopen and replay the archived content as if it were live. That produced false abort events for
# runs that had already been fixed and relaunched - worse than no signal. This tracks a byte offset
# per file and, when a file shrinks or is replaced, skips to the new end instead of replaying.
set -u
B=/mnt/fast-ai/bench-results
FILTER='P[012]-CHAIN-DONE|P[012]-ABORT|Q9-QUEUE-DONE|ABORT:|^G[123] |G[123] mtp|ladder harness exit|START arm=|END   arm=|campaign complete|class_balanced_median|did not become healthy|failed its workload|WARNING: boot'
declare -A OFF=()
while :; do
  shopt -s nullglob
  files=("$B"/chain-logs/q9-p*-chain.log "$B"/chain-logs/q9-queue-driver.log "$B"/chain-logs/q9-arm-*.log "$B"/chain-logs/q9-p1-*.log "$B"/qwen35-9b-*-20260909-*/campaign.log)
  shopt -u nullglob
  for f in "${files[@]}"; do
    case "$f" in *failed*|*aborted*) continue;; esac
    [[ -f "$f" ]] || continue
    sz=$(stat -c %s "$f" 2>/dev/null) || continue
    prev=${OFF[$f]:-}
    if [[ -z "$prev" ]]; then OFF[$f]=$sz; continue; fi           # first sight: start at the end
    if (( sz < prev )); then OFF[$f]=$sz; continue; fi             # rotated/replaced: skip, never replay
    if (( sz > prev )); then
      tail -c +$((prev + 1)) "$f" 2>/dev/null | grep -E "$FILTER" | sed "s|^|$(basename "$(dirname "$f")")/$(basename "$f"): |"
      OFF[$f]=$sz
    fi
  done
  sleep 20
done
