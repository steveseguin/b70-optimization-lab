#!/usr/bin/env bash
set -euo pipefail

log_dir="${SESSION_CACHE_LOG_DIR:-/mnt/fast-ai/bench-results/minimax-m27-b70-serve}"
state_file="${SESSION_CACHE_STATE_FILE:-$log_dir/current-session-cache-profile.json}"
port="${VLLM_PORT:-8000}"
base_url="http://127.0.0.1:${port}"

echo "State file: $state_file"
if [[ -f "$state_file" ]]; then
  cat "$state_file"
else
  echo "(no state file)"
fi

echo
echo "Processes:"
pgrep -a -f '[v]llm serve|[V]LLM::EngineCore|[V]LLM::Worker_TP' || true

echo
echo "Models:"
curl -fsS "$base_url/v1/models" 2>/dev/null || echo "(server not ready at $base_url)"
echo

if [[ "${1:-}" == "--tail" && -f "$state_file" ]]; then
  log_file="$(python3 - <<'PY' "$state_file"
import json
import sys
try:
    print(json.load(open(sys.argv[1])).get("log_file", ""))
except Exception:
    print("")
PY
)"
  if [[ -n "$log_file" && -f "$log_file" ]]; then
    echo
    echo "Tail: $log_file"
    tail -n 80 "$log_file"
  fi
fi
