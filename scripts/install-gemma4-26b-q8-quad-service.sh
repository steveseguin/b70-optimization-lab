#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_unit="gemma4-26b-q8-quad-backends.service"
frontdoor_unit="gemma4-26b-q8-quad-frontdoor.service"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/install-gemma4-26b-q8-quad-service.sh [--start|--restart]

Installs the temporary production Gemma 4 26B Q8 quad service:

- four localhost llama.cpp replicas: 127.0.0.1:19350-19353
- no-auth LAN OpenAI frontdoor: 0.0.0.0:8000
- default profile: GEMMA4_26B_PROFILE=service
- frontend generation cap: 8 active requests
  - GPU0-3: two 64K slots each

This stops the old :8000 frontdoor while the Gemma quad frontdoor is active.
EOF
}

start_now=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --start|--restart)
      start_now=1
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

sudo install -m 0644 "$repo_dir/deploy/systemd/$backend_unit" \
  "/etc/systemd/system/$backend_unit"
sudo install -m 0644 "$repo_dir/deploy/systemd/$frontdoor_unit" \
  "/etc/systemd/system/$frontdoor_unit"
sudo systemctl daemon-reload
sudo systemctl enable "$backend_unit" "$frontdoor_unit"

if [[ "$start_now" == "1" ]]; then
  sudo systemctl disable --now b70-openai-frontdoor.service minimax-openai-frontdoor.service 2>/dev/null || true
  sudo systemctl stop gemma4-26b-q8-llamacpp.service b70-vllm-slot.service minimax-vllm.service 2>/dev/null || true
  sudo systemctl restart "$backend_unit"
  sudo systemctl restart "$frontdoor_unit"
fi

systemctl status "$backend_unit" --no-pager || true
systemctl status "$frontdoor_unit" --no-pager || true
