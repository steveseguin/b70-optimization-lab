#!/usr/bin/env bash
set -euo pipefail

profile="${1:-c4}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$profile" in
  prod|production)
    profile="c1"
    ;;
  c1|c2|c4|c8)
    ;;
  *)
    echo "Usage: $0 {c1|c2|c4|c8|prod} [extra vLLM args...]" >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_dir="${SESSION_CACHE_LOG_DIR:-/mnt/fast-ai/bench-results/minimax-m27-b70-serve}"
state_file="${SESSION_CACHE_STATE_FILE:-$log_dir/current-session-cache-profile.json}"
host="${VLLM_HOST:-0.0.0.0}"
port="${VLLM_PORT:-8000}"
base_url="http://127.0.0.1:${port}"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log_file="$log_dir/serve-session-cache-${profile}-${ts}.log"

mkdir -p "$log_dir"

echo "Stopping existing MiniMax vLLM server, if any..."
pkill -f '[v]llm serve' || true
pkill -f '[V]LLM::EngineCore' || true
pkill -f '[V]LLM::Worker_TP' || true

for _ in $(seq 1 60); do
  if ! pgrep -f '[v]llm serve|[V]LLM::EngineCore|[V]LLM::Worker_TP' >/dev/null; then
    break
  fi
  sleep 1
done

if pgrep -f '[v]llm serve|[V]LLM::EngineCore|[V]LLM::Worker_TP' >/dev/null; then
  echo "Timed out waiting for old vLLM processes to exit:" >&2
  pgrep -a -f '[v]llm serve|[V]LLM::EngineCore|[V]LLM::Worker_TP' >&2 || true
  exit 1
fi

echo "Starting session-cache profile '$profile' on ${host}:${port}"
echo "Log: $log_file"
nohup setsid "$script_dir/serve_session_cache.sh" "$profile" "$@" \
  >"$log_file" 2>&1 < /dev/null &
server_pid=$!

ready_json="$log_dir/serve-session-cache-${profile}-${ts}.models.json"
for _ in $(seq 1 300); do
  if curl -fsS "$base_url/v1/models" >"$ready_json" 2>/dev/null; then
    cat >"$state_file" <<EOF
{
  "profile": "$profile",
  "started_at_utc": "$started_at",
  "host": "$host",
  "port": $port,
  "base_url": "$base_url",
  "launcher_pid": $server_pid,
  "log_file": "$log_file",
  "models_file": "$ready_json"
}
EOF
    echo "Ready: $base_url"
    cat "$ready_json"
    echo
    pgrep -a -f '[v]llm serve|[V]LLM::EngineCore|[V]LLM::Worker_TP' || true
    exit 0
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "Server process exited before readiness." >&2
    tail -n 120 "$log_file" >&2 || true
    exit 1
  fi
  sleep 2
done

echo "Server did not become ready in time." >&2
pgrep -a -f '[v]llm serve|[V]LLM::EngineCore|[V]LLM::Worker_TP' >&2 || true
tail -n 160 "$log_file" >&2 || true
exit 1
