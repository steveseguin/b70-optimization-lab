#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
profile_dir="$repo_dir/configs/model-slots"
slot_dir="/etc/b70-vllm-slot"
current_env="$slot_dir/current.env"
sudo_cmd="${SUDO:-sudo}"

usage() {
  cat >&2 <<'EOF'
Usage:
  scripts/switch-vllm-model-slot.sh list
  scripts/switch-vllm-model-slot.sh status
  scripts/switch-vllm-model-slot.sh switch PROFILE
  scripts/switch-vllm-model-slot.sh restore-minimax

Switches the single active LAN OpenAI-compatible model slot. The switch command
stops the current slot services, stops the older MiniMax-specific services to
avoid two models/endpoints competing for GPUs/port 8000, installs the selected
profile as /etc/b70-vllm-slot/current.env, and starts:

  b70-vllm-slot.service
  b70-openai-frontdoor.service

Use scripts/install-vllm-model-slot-service.sh once before the first switch.
EOF
}

profile_path() {
  local name="${1%.env}"
  if [[ -f "$1" ]]; then
    printf '%s\n' "$1"
  elif [[ -f "$profile_dir/$name.env" ]]; then
    printf '%s\n' "$profile_dir/$name.env"
  else
    return 1
  fi
}

list_profiles() {
  local file name title status modalities hf_id
  for file in "$profile_dir"/*.env; do
    name="$(basename "$file" .env)"
    title="$(awk -F= '/^MODEL_SLOT_TITLE=/{gsub(/^"|"$/, "", $2); print $2; exit}' "$file")"
    status="$(awk -F= '/^MODEL_SLOT_STATUS=/{gsub(/^"|"$/, "", $2); print $2; exit}' "$file")"
    modalities="$(awk -F= '/^MODEL_SLOT_MODALITIES=/{gsub(/^"|"$/, "", $2); print $2; exit}' "$file")"
    hf_id="$(awk -F= '/^MODEL_SLOT_HF_ID=/{gsub(/^"|"$/, "", $2); print $2; exit}' "$file")"
    printf '%-28s %-11s %-11s %s\n' "$name" "${status:-unknown}" "${modalities:-unknown}" "${title:-$hf_id}"
  done
}

ensure_installed() {
  if ! systemctl cat b70-vllm-slot.service >/dev/null 2>&1 || ! systemctl cat b70-openai-frontdoor.service >/dev/null 2>&1; then
    cat >&2 <<EOF
Generic model-slot services are not installed yet.

Install them with:
  $repo_dir/scripts/install-vllm-model-slot-service.sh --profile minimax-m27-c1
EOF
    exit 1
  fi
}

stop_all_slot_services() {
  "$sudo_cmd" systemctl stop b70-openai-frontdoor.service 2>/dev/null || true
  "$sudo_cmd" systemctl stop b70-vllm-slot.service 2>/dev/null || true

  # Stop legacy production services so the host never has two public frontdoors
  # or two model backends competing for B70 VRAM at the same time.
  "$sudo_cmd" systemctl stop minimax-openai-frontdoor.service 2>/dev/null || true
  "$sudo_cmd" systemctl stop minimax-vllm.service 2>/dev/null || true
}

switch_profile() {
  local requested="$1"
  local src
  src="$(profile_path "$requested")" || {
    echo "Unknown model-slot profile: $requested" >&2
    echo "Available profiles:" >&2
    list_profiles >&2
    exit 1
  }

  ensure_installed
  stop_all_slot_services
  "$sudo_cmd" install -d -m 0755 "$slot_dir"
  "$sudo_cmd" install -m 0644 "$src" "$current_env"
  "$sudo_cmd" systemctl daemon-reload
  "$sudo_cmd" systemctl disable minimax-openai-frontdoor.service minimax-vllm.service 2>/dev/null || true
  "$sudo_cmd" systemctl enable b70-vllm-slot.service b70-openai-frontdoor.service
  "$sudo_cmd" systemctl restart b70-vllm-slot.service
  "$sudo_cmd" systemctl restart b70-openai-frontdoor.service
  echo "Switched active model slot to: $(basename "$src" .env)"
  echo "Public OpenAI-compatible endpoint remains: http://0.0.0.0:8000/v1"
}

status_slot() {
  echo "Current profile:"
  if [[ -f "$current_env" ]]; then
    awk -F= '
      /^MODEL_SLOT_(NAME|TITLE|HF_ID|MODALITIES|STATUS)=/ {
        gsub(/^"|"$/, "", $2)
        printf "  %-18s %s\n", $1, $2
      }
    ' "$current_env"
  else
    echo "  none installed at $current_env"
  fi
  echo
  systemctl --no-pager --plain status b70-vllm-slot.service b70-openai-frontdoor.service 2>/dev/null | sed -n '1,80p' || true
  echo
  curl -fsS http://127.0.0.1:8000/status 2>/dev/null || true
  echo
  curl -fsS http://127.0.0.1:8000/v1/models 2>/dev/null || true
  echo
}

cmd="${1:-}"
case "$cmd" in
  list)
    list_profiles
    ;;
  status)
    status_slot
    ;;
  switch)
    if [[ $# -ne 2 ]]; then
      usage
      exit 2
    fi
    switch_profile "$2"
    ;;
  restore-minimax)
    switch_profile minimax-m27-c1
    ;;
  -h|--help|"")
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
