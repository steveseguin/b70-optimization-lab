#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
unit_src="$repo_dir/deploy/systemd/gemma4-26b-q8-llamacpp.service"
unit_dst="/etc/systemd/system/gemma4-26b-q8-llamacpp.service"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/install-gemma4-26b-q8-service.sh [--restart]

Installs and enables the localhost-only Gemma 4 26B Q8 llama.cpp backend:

- service: gemma4-26b-q8-llamacpp.service
- backend: http://127.0.0.1:19350/v1
- default profile: GEMMA4_26B_PROFILE=record

Use --restart to start or restart it immediately. This does not rewire the
public :8000 frontdoor; point the frontdoor at 127.0.0.1:19350 separately if
you want Gemma 26B exposed on the LAN endpoint.
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
sudo systemctl enable gemma4-26b-q8-llamacpp.service

if [[ "$restart_now" == "1" ]]; then
  sudo systemctl restart gemma4-26b-q8-llamacpp.service
fi

systemctl status gemma4-26b-q8-llamacpp.service --no-pager || true
