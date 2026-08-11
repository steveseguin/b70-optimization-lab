#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fleet_unit="muse-glimmer-bf16-fleet.service"
frontdoor_unit="muse-glimmer-frontdoor.service"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/install-muse-glimmer-bf16-service.sh [--start|--restart]

Installs the Muse Glimmer 30B BF16 lossless production fleet:

- two 2xB70 BF16+DFlash replicas: 127.0.0.1:19470-19471 (single slot each)
- no-auth LAN OpenAI frontdoor: 0.0.0.0:8000 (max 2 active generations)

--start stops the Gemma quad services and older :8000 frontdoors first.
EOF
}

start_now=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --start|--restart) start_now=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
  shift
done

sudo install -m 0644 "$repo_dir/deploy/systemd/$fleet_unit" "/etc/systemd/system/$fleet_unit"
sudo install -m 0644 "$repo_dir/deploy/systemd/$frontdoor_unit" "/etc/systemd/system/$frontdoor_unit"
sudo systemctl daemon-reload
sudo systemctl enable "$fleet_unit" "$frontdoor_unit"

if [[ "$start_now" == "1" ]]; then
  sudo systemctl disable --now \
    gemma4-26b-q8-quad-frontdoor.service gemma4-26b-q8-quad-backends.service \
    b70-openai-frontdoor.service minimax-openai-frontdoor.service 2>/dev/null || true
  sudo systemctl stop gemma4-26b-q8-llamacpp.service b70-vllm-slot.service minimax-vllm.service 2>/dev/null || true
  sudo systemctl restart "$fleet_unit"
  sudo systemctl restart "$frontdoor_unit"
fi

systemctl status "$fleet_unit" --no-pager || true
systemctl status "$frontdoor_unit" --no-pager || true
