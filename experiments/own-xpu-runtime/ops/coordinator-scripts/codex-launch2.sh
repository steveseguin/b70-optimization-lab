#!/bin/bash
# Usage: codex-launch2.sh NAME  (brief at scratchpad/codex-NAME-brief.md, log at scratchpad/codex-NAME.log)
# As codex-launch.sh (stdin /dev/null; cores 8-15,24-31; nice 19), plus ONE automatic resume if the run died on the
# API capacity error ("Selected model is at capacity"), after a 3-minute pause (2026-10-19: p58ajb died mid-work).
set -u
S=/tmp/claude-1000/-home-steve/9743941a-5875-4449-b2f0-62a6e15d94f5/scratchpad
cd /home/steve/llm-optimizations
run(){ taskset -c 8-15,24-31 nice -n 19 codex exec -s danger-full-access --skip-git-repo-check --cd /home/steve/llm-optimizations "$1" < /dev/null >> "$S/codex-$2.log" 2>&1; }
run "$(cat "$S/codex-$1-brief.md")" "$1"
if tail -c 4000 "$S/codex-$1.log" | grep -q "Selected model is at capacity"; then
  echo "=== coordinator: capacity error; resuming once after 180 s ===" >> "$S/codex-$1.log"; sleep 180
  run "$(printf '# RESUME: a previous run of this exact brief died on an API capacity error, possibly mid-work. Review git status/diff of your paths and your note, keep valid work, finish the remaining steps, and write READY last.\n\n'; cat "$S/codex-$1-brief.md")" "$1"
fi
