#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
unit_src="$repo_dir/deploy/systemd/minimax-vllm.service"
unit_dst="/etc/systemd/system/minimax-vllm.service"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/install-minimax-vllm-service.sh [--restart]

Installs and enables the systemd service for the production c1 MiniMax vLLM
server. Use --restart to stop any manually started vLLM server and start the
systemd-managed service immediately.
EOF
}

restart_now=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --restart)
      restart_now=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
  shift
done

if [[ ! -f "$unit_src" ]]; then
  echo "Missing unit file: $unit_src" >&2
  exit 1
fi

sudo install -m 0644 "$unit_src" "$unit_dst"
sudo systemctl daemon-reload
sudo systemctl enable minimax-vllm.service

if [[ "$restart_now" == "1" ]]; then
  echo "Stopping manually launched MiniMax vLLM processes, if any..."
  pkill -f '[v]llm serve' || true
  pkill -f '[V]LLM::EngineCore' || true
  pkill -f '[V]LLM::Worker_TP' || true

  for _ in $(seq 1 90); do
    if ! pgrep -f '[v]llm serve|[V]LLM::EngineCore|[V]LLM::Worker_TP' >/dev/null; then
      break
    fi
    sleep 1
  done

  sudo systemctl restart minimax-vllm.service
fi

systemctl status minimax-vllm.service --no-pager || true
