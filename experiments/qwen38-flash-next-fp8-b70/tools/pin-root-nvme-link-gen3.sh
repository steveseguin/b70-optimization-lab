#!/usr/bin/env bash
# Pin the root Samsung 980 PRO link (root port 0000:00:03.1 -> endpoint
# 0000:01:00.0) to PCIe Gen3 (8 GT/s) and disable the drive's autonomous
# power-state transitions. This is the temporary operating state established
# on 2026-09-02 after the discriminator sequence showed Gen4 x4 logging about
# two corrected receiver errors per second on firmware 5B2QGXA7 while Gen3 x4
# logged zero. It is a mitigation, not a repair: the permanent fixes are a
# BIOS-level per-slot link-speed setting, a BIOS/AGESA update, another M.2
# slot, or a different drive.
#
# Run as root (from a boot-time unit or manually). It verifies the exact
# controller identity first, sets the root port's target link speed, retrains,
# waits for the link to settle at 8 GT/s x4, then disables APST.
set -Eeuo pipefail

expected_serial=S6WSNS0T109768K
expected_bdf=0000:01:00.0
root_port=0000:00:03.1

fail() { printf 'pin-root-nvme-link-gen3: FAIL: %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || fail 'must run as root'
serial=$(tr -d '[:space:]' </sys/class/nvme/nvme0/serial)
address=$(tr -d '[:space:]' </sys/class/nvme/nvme0/address)
[[ ${serial} == "${expected_serial}" && ${address} == "${expected_bdf}" ]] ||
  fail "unexpected root NVMe identity: serial=${serial} address=${address}"
[[ -d /sys/bus/pci/devices/${root_port} ]] || fail "root port ${root_port} absent"

# LnkCtl2 bits 3:0 = target link speed (3 = 8 GT/s); LnkCtl bit 5 = retrain.
setpci -s "${root_port}" CAP_EXP+0x30.w=0x0003
lnkctl=$(setpci -s "${root_port}" CAP_EXP+0x10.w)
setpci -s "${root_port}" CAP_EXP+0x10.w="$(printf '0x%04x' $((0x${lnkctl} | 0x20)))"

for _ in $(seq 1 50); do
  speed=$(cat "/sys/bus/pci/devices/${expected_bdf}/current_link_speed")
  width=$(cat "/sys/bus/pci/devices/${expected_bdf}/current_link_width")
  if [[ ${speed} == '8.0 GT/s PCIe' && ${width} == 4 ]]; then
    break
  fi
  sleep 0.1
done
[[ ${speed} == '8.0 GT/s PCIe' && ${width} == 4 ]] ||
  fail "link did not settle at 8 GT/s x4: ${speed} x${width}"

if command -v nvme >/dev/null; then
  nvme set-feature /dev/nvme0 -f 0x0c -v 0 >/dev/null || fail 'could not disable APST'
fi
printf 'pin-root-nvme-link-gen3: %s x%s, APST off, endpoint corrected=%s\n' \
  "${speed}" "${width}" \
  "$(awk '$1=="TOTAL_ERR_COR"{print $2}' "/sys/bus/pci/devices/${expected_bdf}/aer_dev_correctable")"
