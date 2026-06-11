#!/usr/bin/env bash
set -euo pipefail

apply=0
if [[ "${1:-}" == "--apply" ]]; then
  apply=1
elif [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  scripts/tune-b70-runtime-performance-policy.sh          # dry-run
  sudo scripts/tune-b70-runtime-performance-policy.sh --apply

Applies reversible runtime policies for Intel Arc Pro B70 inference:
  - PCIe ASPM policy -> performance
  - B70 endpoints and PCIe bridge path power/control -> on

This does not change BIOS settings and cannot repair a link that is already
trained or reported as a low max width/speed. Re-run the host-link audit after.
USAGE
  exit 0
fi

write_value() {
  local value="$1"
  local path="$2"

  if [[ ! -e "$path" ]]; then
    echo "missing $path"
    return
  fi

  local current="n/a"
  if [[ -r "$path" ]]; then
    current="$(tr -d '\n' <"$path")"
  fi

  if [[ "$apply" -eq 0 ]]; then
    echo "would set $path: '$current' -> '$value'"
    return
  fi

  if [[ "$(id -u)" -ne 0 ]]; then
    echo "error: --apply requires root for $path" >&2
    exit 1
  fi

  echo "$value" >"$path"
  local after
  after="$(tr -d '\n' <"$path")"
  echo "set $path: '$current' -> '$after'"
}

collect_path_bdfs() {
  local endpoint="$1"
  local real
  real="$(readlink -f "/sys/bus/pci/devices/$endpoint")"
  IFS='/' read -r -a parts <<<"$real"
  for part in "${parts[@]}"; do
    if [[ "$part" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}[.][0-9a-fA-F]$ ]]; then
      echo "$part"
    fi
  done
}

echo "# B70 runtime performance policy"
if [[ "$apply" -eq 1 ]]; then
  echo "mode=apply"
else
  echo "mode=dry-run"
fi

mapfile -t b70_bdfs < <(lspci -Dnnd 8086:e223 | awk '{print $1}')
if [[ "${#b70_bdfs[@]}" -eq 0 ]]; then
  echo "error: no Intel Arc Pro B70 endpoints found with PCI ID 8086:e223" >&2
  exit 1
fi

echo
echo "# PCIe ASPM"
write_value performance /sys/module/pcie_aspm/parameters/policy

echo
echo "# Endpoint and bridge runtime power"
declare -A seen=()
for bdf in "${b70_bdfs[@]}"; do
  while IFS= read -r path_bdf; do
    [[ -n "$path_bdf" ]] || continue
    if [[ -n "${seen[$path_bdf]:-}" ]]; then
      continue
    fi
    seen[$path_bdf]=1
    write_value on "/sys/bus/pci/devices/$path_bdf/power/control"
  done < <(collect_path_bdfs "$bdf")
done

echo
echo "# Next"
echo "Run: scripts/audit-b70-host-links.sh"
echo "Then rerun the p512/n512 direct speed control and frontdoor exact-OK smoke."
