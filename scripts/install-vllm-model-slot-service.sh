#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
slot_dir="/etc/b70-vllm-slot"
profile="minimax-m27-c1"
start_now=0
enable_now=0
sudo_cmd="${SUDO:-sudo}"

usage() {
  cat >&2 <<'EOF'
Usage: scripts/install-vllm-model-slot-service.sh [--profile NAME] [--enable] [--start]

Installs the generic single-model vLLM slot services:

- b70-vllm-slot.service: one localhost-only vLLM backend on 127.0.0.1:18080
- b70-openai-frontdoor.service: no-auth LAN OpenAI-compatible frontdoor on
  0.0.0.0:8000

The active model is selected by /etc/b70-vllm-slot/current.env. Use
scripts/switch-vllm-model-slot.sh to change it. Only one model should be loaded
at a time.

By default this only installs files. Use --enable to enable the generic slot at
boot, or --start to enable it and switch to the selected profile now.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      profile="${2:?missing profile name}"
      shift
      ;;
    --enable)
      enable_now=1
      ;;
    --start|--restart)
      start_now=1
      enable_now=1
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

profile_src="$repo_dir/configs/model-slots/${profile%.env}.env"
if [[ ! -f "$profile_src" ]]; then
  echo "Unknown model-slot profile: $profile" >&2
  echo "Available profiles:" >&2
  find "$repo_dir/configs/model-slots" -maxdepth 1 -name '*.env' -printf '  %f\n' | sed 's/\.env$//' >&2
  exit 1
fi

"$sudo_cmd" install -d -m 0755 "$slot_dir"
"$sudo_cmd" install -m 0644 "$profile_src" "$slot_dir/current.env"
"$sudo_cmd" install -m 0644 "$repo_dir/deploy/systemd/b70-vllm-slot.service" /etc/systemd/system/b70-vllm-slot.service
"$sudo_cmd" install -m 0644 "$repo_dir/deploy/systemd/b70-openai-frontdoor.service" /etc/systemd/system/b70-openai-frontdoor.service
"$sudo_cmd" systemctl daemon-reload

if [[ "$enable_now" == "1" ]]; then
  "$sudo_cmd" systemctl enable b70-vllm-slot.service b70-openai-frontdoor.service
fi

if [[ "$start_now" == "1" ]]; then
  "$repo_dir/scripts/switch-vllm-model-slot.sh" switch "$profile"
else
  echo "Installed model-slot services with current profile: $profile"
  if [[ "$enable_now" == "1" ]]; then
    echo "Enabled generic model-slot services for boot."
  else
    echo "Services were not enabled or started."
  fi
  echo "Start/switch with: $repo_dir/scripts/switch-vllm-model-slot.sh switch $profile"
fi
