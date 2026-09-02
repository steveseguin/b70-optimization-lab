#!/usr/bin/env bash
# Unattended Supermicro M12SWA-TF BIOS update through the board's built-in
# UEFI shell, without a USB stick or an installed-OS flasher.
#
# Mechanism (from the vendor package and the SAA 1.3.0 UEFI user guide):
#   * The BIOS zip ships SAA.efi, which uploads the image to the BMC over the
#     internal Redfish host interface and lets the BMC program the SPI flash.
#     Its in-band use "does not require node product key activation".
#   * The image and SAA.efi are staged on the EFI System Partition under
#     \M12BIOS. A one-shot \startup.nsh on the ESP root runs the update with
#     --preserve_setting --reboot. BootNext is pointed at the built-in EFI
#     shell (Boot0001), which auto-executes startup.nsh after its countdown.
#   * SAA reboots the host when the BMC finishes; BootNext is consumed, so the
#     next boot is the normal Ubuntu entry. --disarm removes the script.
#
# Modes:
#   --preflight   verify every precondition; change nothing
#   --arm         preflight, write startup.nsh, set BootNext=0001 (no reboot)
#   --disarm      remove startup.nsh and clear BootNext
#   --reboot-now  arm, then reboot immediately (requires --confirm FLASH-BIOS-2.4a)
#
# The BMC ADMIN password is read from a root-only file and written into the
# ESP script only for the duration of the flash; --disarm deletes it.
set -Eeuo pipefail

expected_bin_sha=14e5bbbc24df76849e5fc0edf888d89aaefcbf10cb08527abc51d4a9cfc04074
expected_saa_sha=d4149bccee97461d1b3adf34f8c127a6470cf9e55883d2e89f3a1833c9dfd0c0
bios_bin=BIOS_M12SWA-TF-1C1C_20250717_2.4a_STDsp.bin
esp=/boot/efi
esp_dir=${esp}/M12BIOS
startup=${esp}/startup.nsh
shell_entry=0001
bmc_host=169.254.3.254
bmc_user=ADMIN
bmc_password_file=/home/steve/.config/bmc/admin_password
sudo_password_file=/home/steve/SUDOPASSWORD.txt
expected_board=M12SWA-TF
expected_current_bios=2.0b
runtime_clear=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/check-q38-recovery-runtime-clear.sh

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
root() { sudo -S -p '' "$@" <"${sudo_password_file}"; }

mode=${1:-}
confirm=${3:-}
[[ ${2:-} == --confirm || -z ${2:-} ]] || fail "unexpected argument: $2"
case "${mode}" in --preflight|--arm|--disarm|--reboot-now) ;; *) fail 'usage: --preflight | --arm | --disarm | --reboot-now --confirm FLASH-BIOS-2.4a' ;; esac
[[ ${EUID} -ne 0 ]] || fail 'run as the ordinary user'

if [[ ${mode} == --disarm ]]; then
  root rm -f "${startup}"
  root efibootmgr -N >/dev/null 2>&1 || true
  root sync
  printf 'disarmed: startup.nsh removed, BootNext cleared\n'
  root efibootmgr | grep -E 'BootNext|BootCurrent|BootOrder' || true
  exit 0
fi

# ---- preflight ------------------------------------------------------------
[[ -r ${bmc_password_file} ]] || fail 'BMC password file unreadable'
pw=$(<"${bmc_password_file}")
[[ ${#pw} -ge 8 ]] || fail 'BMC password file is too short'
board=$(root dmidecode -s baseboard-product-name | tr -d '[:space:]')
bios=$(root dmidecode -s bios-version | tr -d '[:space:]')
[[ ${board} == "${expected_board}" ]] || fail "board is ${board}, not ${expected_board}"
[[ ${bios} == "${expected_current_bios}" ]] || fail "BIOS is ${bios}; this helper is frozen for ${expected_current_bios} -> 2.4a"
findmnt -no FSTYPE "${esp}" | grep -q vfat || fail "${esp} is not a mounted vfat ESP"
[[ -f ${esp_dir}/${bios_bin} && -f ${esp_dir}/SAA.efi ]] || fail 'staged image or SAA.efi missing from the ESP'
[[ $(sha256sum "${esp_dir}/${bios_bin}" | cut -d' ' -f1) == "${expected_bin_sha}" ]] || fail 'staged BIOS image hash mismatch'
[[ $(sha256sum "${esp_dir}/SAA.efi" | cut -d' ' -f1) == "${expected_saa_sha}" ]] || fail 'staged SAA.efi hash mismatch'
root efibootmgr | grep -qE "^Boot${shell_entry}\*? UEFI: Built-in EFI Shell" || fail "Boot${shell_entry} is not the built-in EFI shell"
# BMC host interface must answer with the stored credential.
sys_json=$(curl -sk -m 15 -u "${bmc_user}:${pw}" "https://${bmc_host}/redfish/v1/Systems/1") || fail 'BMC Redfish host interface unreachable'
python3 - "${sys_json}" "${expected_board}" "${expected_current_bios}" <<'PY' || fail 'BMC did not confirm board/BIOS with the stored credential'
import json, sys
d = json.loads(sys.argv[1])
assert d.get("Model") == sys.argv[2], d.get("Model")
assert d.get("BiosVersion") == sys.argv[3], d.get("BiosVersion")
assert d.get("PowerState") == "On"
PY
# No GPU/model work may be in flight.
"${runtime_clear}" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("status")=="clear" else 1)' || fail 'runtime conflict scan is not clear'
if fuser -s /dev/dri/renderD* 2>/dev/null; then fail 'a process holds a B70 render node'; fi
# Removable live media would compete for fs0: in the shell.
if lsblk -dno LABEL,TRAN | grep -iE 'ubuntu.*usb|usb.*ubuntu' >/dev/null; then
  fail 'the Ubuntu live USB is still attached; remove it so the ESP is fs0: in the shell'
fi
printf 'preflight passed: board %s, BIOS %s, ESP staged, shell entry Boot%s, BMC reachable\n' "${board}" "${bios}" "${shell_entry}"
[[ ${mode} != --preflight ]] || exit 0

# ---- arm ------------------------------------------------------------------
tmp=$(mktemp)
trap 'rm -f "${tmp}"' EXIT
{
  printf '@echo -off\r\n'
  printf 'echo M12SWA-TF BIOS 2.4a unattended update starting\r\n'
  for i in 0 1 2 3 4 5 6 7; do
    printf 'if exist fs%d:\\M12BIOS\\SAA.efi then\r\n' "$i"
    printf '  fs%d:\r\n' "$i"
    printf '  cd \\M12BIOS\r\n'
    printf '  echo running SAA on fs%d\r\n' "$i"
    # --preserve_setting is rejected on this platform (SAA exit 38, 2026-09-02
    # 08:16 attempt), so settings may reset to defaults; verify after boot.
    printf '  SAA.efi -I Redfish_HI -u %s -p %s -c UpdateBios --file %s --reboot >a saa-update.log\r\n' "${bmc_user}" "${pw}" "${bios_bin}"
    printf '  echo SAA returned; rebooting in 30 seconds\r\n'
    printf '  stall 30000000\r\n'
    printf '  reset\r\n'
    printf 'endif\r\n'
  done
  printf 'echo staged files not found on any fs mapping; rebooting\r\n'
  printf 'stall 30000000\r\n'
  printf 'reset\r\n'
} >"${tmp}"
root install -m 0600 "${tmp}" "${startup}"
root efibootmgr --bootnext "${shell_entry}" >/dev/null
root sync
printf 'armed: %s written, BootNext=%s\n' "${startup}" "${shell_entry}"
root efibootmgr | grep -E 'BootNext|BootOrder'
if [[ ${mode} == --reboot-now ]]; then
  [[ ${confirm} == FLASH-BIOS-2.4a ]] || fail 'pass --confirm FLASH-BIOS-2.4a to reboot into the updater'
  printf 'rebooting into the built-in EFI shell now\n'
  root systemctl reboot
fi
