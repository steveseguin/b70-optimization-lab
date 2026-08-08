#!/usr/bin/env bash
# Read-only PCIe ancestry and negotiated-link report for DRM/GPU devices.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/report-pcie-topology.sh [0000:BB:DD.F ...]

With no arguments, report each PCI device exposed through /sys/class/drm/card*.
With arguments, report only the selected full-domain BDFs.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

declare -a endpoints=()
if (($#)); then
  endpoints=("$@")
else
  declare -a discovered=()
  for card in /sys/class/drm/card*; do
    [[ "$(basename "$card")" =~ ^card[0-9]+$ ]] || continue
    device="$card/device"
    [[ -e "$device" ]] || continue
    discovered+=("$(basename "$(realpath "$device")")")
  done
  if ((${#discovered[@]})); then
    mapfile -t endpoints < <(printf '%s\n' "${discovered[@]}" | sort -u)
  fi
fi

if ((${#endpoints[@]} == 0)); then
  echo "No PCI DRM devices found; provide one or more full-domain BDFs." >&2
  exit 1
fi

read_attr() {
  local path="$1"
  if [[ -r "$path" ]]; then
    tr -d '\n' < "$path"
  else
    printf 'n/a'
  fi
}

read_width() {
  local width
  width="$(read_attr "$1")"
  if [[ "$width" == "n/a" ]]; then
    printf '%s' "$width"
  else
    printf 'x%s' "$width"
  fi
}

for raw_endpoint in "${endpoints[@]}"; do
  endpoint="${raw_endpoint,,}"
  if [[ ! "$endpoint" =~ ^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]$ ]]; then
    echo "Invalid full-domain BDF: $raw_endpoint" >&2
    exit 2
  fi

  device_path="/sys/bus/pci/devices/$endpoint"
  if [[ ! -e "$device_path" ]]; then
    echo "PCI device is not present: $endpoint" >&2
    exit 2
  fi

  resolved="$(realpath "$device_path")"
  printf 'endpoint=%s\n' "$endpoint"
  printf 'sysfs_path=%s\n' "$resolved"
  printf 'bdf\trole\tcurrent_speed\tcurrent_width\tmax_speed\tmax_width\tdescription\n'

  IFS='/' read -r -a components <<< "$resolved"
  for component in "${components[@]}"; do
    [[ "$component" =~ ^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]$ ]] || continue
    node_path="/sys/bus/pci/devices/$component"
    role=upstream
    [[ "$component" == "$endpoint" ]] && role=endpoint
    description=n/a
    if command -v lspci >/dev/null 2>&1; then
      description="$(lspci -D -s "$component" -nn 2>/dev/null || true)"
      [[ -n "$description" ]] || description=n/a
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$component" \
      "$role" \
      "$(read_attr "$node_path/current_link_speed")" \
      "$(read_width "$node_path/current_link_width")" \
      "$(read_attr "$node_path/max_link_speed")" \
      "$(read_width "$node_path/max_link_width")" \
      "$description"
  done
  printf '\n'
done
