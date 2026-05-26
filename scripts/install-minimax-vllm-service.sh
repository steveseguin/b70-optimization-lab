#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
vllm_unit_src="$repo_dir/deploy/systemd/minimax-vllm.service"
frontdoor_unit_src="$repo_dir/deploy/systemd/minimax-openai-frontdoor.service"
vllm_unit_dst="/etc/systemd/system/minimax-vllm.service"
frontdoor_unit_dst="/etc/systemd/system/minimax-openai-frontdoor.service"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/install-minimax-vllm-service.sh [--restart]

Installs and enables the systemd services for the production c1 MiniMax stack:

- minimax-vllm.service: localhost-only vLLM backend on 127.0.0.1:18080
- minimax-openai-frontdoor.service: no-auth LAN OpenAI-compatible frontdoor on
  0.0.0.0:8000

Use --restart to stop any manually started vLLM server and start the
systemd-managed stack immediately.
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

if [[ ! -f "$vllm_unit_src" ]]; then
  echo "Missing unit file: $vllm_unit_src" >&2
  exit 1
fi
if [[ ! -f "$frontdoor_unit_src" ]]; then
  echo "Missing unit file: $frontdoor_unit_src" >&2
  exit 1
fi

sudo install -m 0644 "$vllm_unit_src" "$vllm_unit_dst"
sudo install -m 0644 "$frontdoor_unit_src" "$frontdoor_unit_dst"
sudo systemctl daemon-reload
sudo systemctl enable minimax-vllm.service
sudo systemctl enable minimax-openai-frontdoor.service

if [[ "$restart_now" == "1" ]]; then
  echo "Stopping existing frontdoor and manually launched MiniMax vLLM processes, if any..."
  sudo systemctl stop minimax-openai-frontdoor.service || true
  sudo systemctl stop minimax-vllm.service || true
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
  sudo systemctl restart minimax-openai-frontdoor.service
fi

systemctl status minimax-vllm.service --no-pager || true
systemctl status minimax-openai-frontdoor.service --no-pager || true
