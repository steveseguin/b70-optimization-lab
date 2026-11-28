#!/bin/bash
# check-journal-faults.sh [since_timestamp]:
# Checks kernel journal since <since_timestamp> (default: current boot) for exact xe / GPU fault signatures.
# Uses specific signatures per AGENTS.md (avoids generic false positives like "hang").
set -u
since=${1:-}
SIG='Fault response|CAT error|engine reset|coredump|GuC.*(crash|fault|failed)|device inaccessible|Buffer eviction failed|Resetting gt'

if [ -n "$since" ]; then
    hits=$(journalctl -k --no-pager --since "$since" 2>/dev/null | grep -E "$SIG" || true)
else
    hits=$(journalctl -k -b --no-pager 2>/dev/null | grep -E "$SIG" || true)
fi

if [ -n "$hits" ]; then
    echo "FAIL journal-faults: GPU/xe fault signature(s) found${since:+ since $since}:"
    echo "$hits" | head -n 20
    exit 1
fi
echo "PASS journal-faults: 0 GPU fault lines${since:+ since $since}"
exit 0
