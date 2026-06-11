#!/usr/bin/env bash
set -euo pipefail

read_attr() {
  local path="$1"
  if [[ -r "$path" ]]; then
    tr -d '\n' <"$path"
  else
    printf 'n/a'
  fi
}

print_pci_node() {
  local bdf="$1"
  local dev="/sys/bus/pci/devices/$bdf"
  if [[ ! -e "$dev" ]]; then
    printf '%s missing\n' "$bdf"
    return
  fi

  printf '%s vendor=%s device=%s class=%s current=%s_x%s max=%s_x%s power=%s numa=%s\n' \
    "$bdf" \
    "$(read_attr "$dev/vendor")" \
    "$(read_attr "$dev/device")" \
    "$(read_attr "$dev/class")" \
    "$(read_attr "$dev/current_link_speed")" \
    "$(read_attr "$dev/current_link_width")" \
    "$(read_attr "$dev/max_link_speed")" \
    "$(read_attr "$dev/max_link_width")" \
    "$(read_attr "$dev/power/control")" \
    "$(read_attr "$dev/numa_node")"
}

echo "# B70 host/link audit"
date -Iseconds
uname -a
if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  echo "os=${PRETTY_NAME:-unknown}"
fi

echo
echo "# PCIe ASPM policy"
read_attr /sys/module/pcie_aspm/parameters/policy
echo

echo
echo "# xpu-smi discovery"
if command -v xpu-smi >/dev/null 2>&1; then
  timeout 10 xpu-smi discovery || true
else
  echo "xpu-smi not found"
fi

echo
echo "# B70 endpoint link state"
mapfile -t b70_bdfs < <(lspci -Dnnd 8086:e223 | awk '{print $1}')
if [[ "${#b70_bdfs[@]}" -eq 0 ]]; then
  echo "no 8086:e223 endpoints found"
else
  for bdf in "${b70_bdfs[@]}"; do
    print_pci_node "$bdf"
  done
fi

echo
echo "# B70 upstream path link state"
for bdf in "${b70_bdfs[@]:-}"; do
  dev="/sys/bus/pci/devices/$bdf"
  real="$(readlink -f "$dev")"
  echo "endpoint=$bdf path=$real"
  IFS='/' read -r -a parts <<<"$real"
  for part in "${parts[@]}"; do
    if [[ "$part" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}[.][0-9a-fA-F]$ ]]; then
      print_pci_node "$part"
    fi
  done
done

echo
echo "# Current B70 power/frequency snapshots"
if command -v xpu-smi >/dev/null 2>&1; then
  for dev_id in 0 1 2 3; do
    echo "device=$dev_id"
    timeout 10 xpu-smi stats -d "$dev_id" | rg 'GPU Power \(W\)|GPU Frequency \(MHz\)|GPU Memory Used' || true
  done
fi
