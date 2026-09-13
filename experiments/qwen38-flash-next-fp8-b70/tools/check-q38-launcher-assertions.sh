#!/usr/bin/env bash
# Offline preflight for a frozen Flash-Next launcher: its bare (set -e, no message) grep assertions on the
# derived server source are evaluated against the derived-source-only output, naming the first that fails.
# A376 (2026-09-13) died this way with an empty host log after MAXLEN: moved the derived context check.
# usage: check-q38-launcher-assertions.sh <attempt> <launcher>  — evaluates the launcher's bare derived-source assertions
a=$1; l=$2; d=$(mktemp); env Q38_A${a}_DERIVED_SOURCE_ONLY=1 bash "$l" >"$d" 2>/dev/null || { echo "A$a: derived-source-only mode failed"; exit 1; }
t=$(mktemp); { echo "derived=$d"; echo 'set -e; trap '"'"'echo "A'"$a"': FAILED assertion at line $LINENO: $BASH_COMMAND"'"'"' ERR'; grep -E '^\s*!? ?grep -F.*"\$derived"|^\s*\[\[ "\$\(grep -F.*"\$derived"\)" == [0-9]+ \]\]' "$l"; } >"$t"
n=$(grep -c derived "$t"); bash "$t" && echo "A$a: all $((n-1)) derived-source assertions hold"; rm -f "$d" "$t"
