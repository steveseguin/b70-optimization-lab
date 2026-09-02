#!/usr/bin/env bash
# Fail-closed in-place (installed OS) runner for Samsung's official 980 PRO
# firmware utility. This is the no-live-USB alternative to
# run-samsung-980-pro-official-updater-from-live.sh: Samsung's own statically
# linked `fumagician` performs the NVMe firmware download and commit while the
# drive stays usable, and the new image activates at the next controller reset
# (a full power-off is required afterwards anyway for the SSD reseat).
#
# It never selects a drive or raw image, never reboots, and refuses to run
# unless every identity, hash, process, link, SMART, swap, and staging gate
# passes twice (once before staging, once immediately before exec).
#
# Usage:
#   run-samsung-980-pro-official-updater-in-place.sh --dry-run
#   run-samsung-980-pro-official-updater-in-place.sh --vendor-dry-run
#   run-samsung-980-pro-official-updater-in-place.sh \
#       --confirm UPDATE-S6WSNS0T109768K-TO-5B2QGXA7
#
# --dry-run runs every gate and staging step but never starts the utility.
# --vendor-dry-run starts Samsung's utility and answers N at its confirmation,
#   proving the utility detects the drive on this kernel without writing.
set -Eeuo pipefail

expected_serial=S6WSNS0T109768K
expected_model='Samsung SSD 980 PRO with Heatsink 1TB'
expected_bdf=0000:01:00.0
expected_root_port=0000:00:03.1
expected_old_firmware=4B2QGXA7
expected_new_firmware=5B2QGXA7
expected_binary_sha=a268c44020a1226df198237c16f315dc9e7dd120186021ac430118dac4cd9153
expected_dsrd_sha=ba85e97c70f1f8c3f6abafcda7c9ba977bcad75f3ea2e9913ff98f69c9ba3c7c
expected_payload_sha=9ecee639ce2c8d34cb8ba13cd2d2a4955e094100394dba1c59ed44b29584a85e
source_dir=/mnt/usb-models/tools/samsung-980-pro-firmware/live-updater
evidence_root=/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host
sudo_password_file=/home/steve/SUDOPASSWORD.txt
max_temperature_c=60
min_mem_available_kib=16000000

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
driver="${script_dir}/drive-samsung-fumagician-pty.py"
runtime_clear="${script_dir}/check-q38-recovery-runtime-clear.sh"

mode=confirm
confirm_token=
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) mode=dry-run ;;
    --vendor-dry-run) mode=vendor-dry-run ;;
    --confirm) shift; confirm_token=${1:-} ;;
    --source-dir) shift; source_dir=${1:?} ;;
    --evidence-root) shift; evidence_root=${1:?} ;;
    --sudo-password-file) shift; sudo_password_file=${1:?} ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

root() {
  # Never echo the password; sudo reads it from the file on stdin.
  sudo -S -p '' "$@" <"${sudo_password_file}"
}

digest() {
  sha256sum "$1" | cut -d' ' -f1
}

[[ ${EUID} -ne 0 ]] || fail 'run as the ordinary user; privileged steps use sudo'
[[ -r ${sudo_password_file} ]] || fail 'sudo password file is unreadable'
[[ -x ${driver} ]] || fail "missing pty driver: ${driver}"
[[ -x ${runtime_clear} ]] || fail "missing runtime-clear checker: ${runtime_clear}"
for tool in nvme lsblk findmnt swapon fuser jq python3 sha256sum; do
  command -v "$tool" >/dev/null || fail "missing tool: $tool"
done
root true || fail 'sudo authentication failed'

# ---- installed-OS binding: root must be the target drive itself ----------
root_source=$(findmnt -nro SOURCE /)
[[ ${root_source} == /dev/nvme0n1p* ]] ||
  fail "root is ${root_source}; this helper targets the installed OS on nvme0"
cmdline=$(</proc/cmdline)
[[ " ${cmdline} " != *' boot=casper '* ]] || fail 'this is a live boot; use the live helper'

# ---- untouched vendor files -----------------------------------------------
for name in fumagician DSRD.enc 5B2QGXA7.enc; do
  [[ -f ${source_dir}/${name} && ! -L ${source_dir}/${name} ]] ||
    fail "missing or linked vendor file: ${source_dir}/${name}"
done
[[ $(digest "${source_dir}/fumagician") == "${expected_binary_sha}" ]] ||
  fail 'Samsung utility hash mismatch'
[[ $(digest "${source_dir}/DSRD.enc") == "${expected_dsrd_sha}" ]] ||
  fail 'Samsung DSRD hash mismatch'
[[ $(digest "${source_dir}/5B2QGXA7.enc") == "${expected_payload_sha}" ]] ||
  fail 'Samsung firmware payload hash mismatch'

aer_total() {
  awk -v key="$2" '$1==key{print $2}' "/sys/bus/pci/devices/$1/aer_dev_$3"
}

target_firmware=
verify_target_state() {
  local controller_path serial model firmware block_path vendor other_model
  local address afi frs1 swap_output mem_avail
  local found=0
  for controller_path in /sys/class/nvme/nvme*; do
    serial=$(tr -d '[:space:]' <"${controller_path}/serial")
    model=$(sed 's/[[:space:]]*$//' "${controller_path}/model")
    if [[ ${model,,} == *samsung* && ${serial} != "${expected_serial}" ]]; then
      fail "another Samsung NVMe is present: ${model} serial ${serial}"
    fi
    if [[ ${serial} == "${expected_serial}" ]]; then
      [[ ${controller_path##*/} == nvme0 ]] || fail 'target serial is not nvme0'
      [[ ${model} == "${expected_model}" ]] || fail "unexpected model: ${model}"
      address=$(tr -d '[:space:]' <"${controller_path}/address")
      [[ ${address} == "${expected_bdf}" ]] || fail "unexpected BDF: ${address}"
      target_firmware=$(tr -d '[:space:]' <"${controller_path}/firmware_rev")
      found=1
    fi
  done
  [[ ${found} -eq 1 ]] || fail "target serial ${expected_serial} is absent"
  [[ ${target_firmware} == "${expected_old_firmware}" ]] ||
    fail "expected ${expected_old_firmware}, found ${target_firmware}"
  for block_path in /sys/block/sd*; do
    [[ -e ${block_path} ]] || continue
    vendor=$(sed 's/[[:space:]]*$//' "${block_path}/device/vendor" 2>/dev/null || true)
    other_model=$(sed 's/[[:space:]]*$//' "${block_path}/device/model" 2>/dev/null || true)
    [[ ${vendor,,}:${other_model,,} != *samsung* ]] ||
      fail "another Samsung block device is present: ${block_path##*/}"
  done
  # Firmware slot state: slot 1 active, nothing pending.
  afi=$(root nvme fw-log /dev/nvme0 | awk '$1=="afi"{print $3}')
  frs1=$(root nvme fw-log /dev/nvme0 | awk '$1=="frs1"{print $4}' | tr -d '()')
  [[ ${afi} == 0x1 ]] || fail "unexpected firmware activation state afi=${afi}"
  [[ ${frs1} == "${expected_old_firmware}" ]] || fail "slot 1 holds ${frs1}"
  # Link must have no uncorrected history and no root-port corrected events.
  [[ $(aer_total "${expected_bdf}" TOTAL_ERR_NONFATAL nonfatal) == 0 ]] ||
    fail 'endpoint has non-fatal AER history; do not flash across this link'
  [[ $(aer_total "${expected_bdf}" TOTAL_ERR_FATAL fatal) == 0 ]] ||
    fail 'endpoint has fatal AER history'
  [[ $(aer_total "${expected_root_port}" TOTAL_ERR_COR correctable) == 0 ]] ||
    fail 'root port reports corrected events'
  [[ $(cat "/sys/bus/pci/devices/${expected_bdf}/current_link_speed") == '16.0 GT/s PCIe' ]] ||
    fail 'link is not at 16 GT/s'
  # SMART must be clean and cool.
  root nvme smart-log /dev/nvme0 -o json >"${work}/smart.json"
  jq -e '.critical_warning == 0 and .media_errors == 0 and .num_err_log_entries == 0' \
    "${work}/smart.json" >/dev/null || fail 'SMART is not clean'
  [[ $(jq -r '.temperature - 273' "${work}/smart.json") -le ${max_temperature_c} ]] ||
    fail 'drive is above the allowed temperature'
  # No GPU/model runtime and no render-node users.
  "${runtime_clear}" >"${work}/runtime-clear.json" ||
    fail 'runtime conflict scan did not return clear'
  [[ $(jq -r '.status' "${work}/runtime-clear.json") == clear ]] ||
    fail 'runtime conflict scan status is not clear'
  if fuser -s /dev/dri/renderD* 2>/dev/null; then
    fail 'a process holds a B70 render node'
  fi
  mem_avail=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
  [[ ${mem_avail} -ge ${min_mem_available_kib} ]] || fail "MemAvailable ${mem_avail} KiB too low"
  if [[ ${mode} != dry-run ]]; then
    swap_output=$(swapon --show=NAME --noheadings)
    [[ -z ${swap_output//[[:space:]]/} ]] || fail 'swap is still active'
  fi
}

work=$(mktemp -d /dev/shm/samsung-980-pro-fw-work.XXXXXX)
stage=
cleanup() {
  [[ -n ${stage} ]] && root rm -rf -- "${stage}" >/dev/null 2>&1 || true
  rm -rf -- "${work}"
}
trap cleanup EXIT

if [[ ${mode} == confirm ]]; then
  [[ ${confirm_token} == "UPDATE-${expected_serial}-TO-${expected_new_firmware}" ]] ||
    fail "pass --confirm UPDATE-${expected_serial}-TO-${expected_new_firmware} to flash"
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
evidence="${evidence_root}/${stamp}-samsung-980-pro-in-place-${mode}"
mkdir -p "${evidence}"
[[ $(findmnt -nro SOURCE --target "${evidence}") != /dev/nvme0n1p* ]] ||
  fail 'evidence directory must not live on the target drive'

# Turn swap off before the pre-exec gate (real and vendor-dry-run modes).
if [[ ${mode} != dry-run ]]; then
  swapon --show >"${evidence}/swap-before.txt" || true
  root swapoff -a || fail 'swapoff failed'
fi

verify_target_state
cp "${work}/smart.json" "${evidence}/smart-before.json"
cp "${work}/runtime-clear.json" "${evidence}/runtime-clear-before.json"
root nvme fw-log /dev/nvme0 >"${evidence}/fw-log-before.txt"
root nvme id-ctrl /dev/nvme0 | grep -E '^(sn|mn|fr|frmw|fwug) ' >"${evidence}/id-ctrl-before.txt"
cat /sys/bus/pci/devices/${expected_bdf}/aer_dev_correctable >"${evidence}/aer-endpoint-before.txt"
cat /sys/bus/pci/devices/${expected_root_port}/aer_dev_correctable >"${evidence}/aer-root-before.txt"
cat /proc/sys/kernel/random/boot_id >"${evidence}/boot_id"
uname -r >"${evidence}/kernel"
sha256sum "${driver}" "${BASH_SOURCE[0]}" >"${evidence}/helper-sha256"

# Stage the untouched vendor files in root-owned tmpfs so nothing is read from
# the drive being flashed while the utility runs.
stage=$(root mktemp -d /dev/shm/samsung-980-pro-fw.XXXXXX)
root chmod 0755 "${stage}"
root install -o root -g root -m 0555 "${source_dir}/fumagician" "${stage}/fumagician"
root install -o root -g root -m 0444 "${source_dir}/DSRD.enc" "${stage}/DSRD.enc"
root install -o root -g root -m 0444 "${source_dir}/5B2QGXA7.enc" "${stage}/5B2QGXA7.enc"
root install -o root -g root -m 0555 "${driver}" "${stage}/driver.py"
[[ $(digest "${stage}/fumagician") == "${expected_binary_sha}" ]] || fail 'staged utility hash mismatch'
[[ $(digest "${stage}/DSRD.enc") == "${expected_dsrd_sha}" ]] || fail 'staged DSRD hash mismatch'
[[ $(digest "${stage}/5B2QGXA7.enc") == "${expected_payload_sha}" ]] || fail 'staged payload hash mismatch'
[[ $(digest "${stage}/driver.py") == $(digest "${driver}") ]] || fail 'staged driver hash mismatch'
sync

verify_target_state
printf '%s\n' \
  'Samsung 980 PRO in-place firmware gate passed.' \
  "Target: ${expected_model} serial ${expected_serial} at ${expected_bdf}" \
  "Current firmware: ${expected_old_firmware}; required: ${expected_new_firmware}" \
  "Mode: ${mode}" \
  "Evidence: ${evidence}"

if [[ ${mode} == dry-run ]]; then
  printf '%s\n' 'DRY RUN: every gate passed; the utility was not started.' \
    'Rerun with --confirm UPDATE-'"${expected_serial}"'-TO-'"${expected_new_firmware}"' to flash.'
  echo '{"status":"dry-run-pass"}' >"${evidence}/summary.json"
  exit 0
fi

answer=N
[[ ${mode} == confirm ]] && answer=Y
set +e
root python3 "${stage}/driver.py" --cwd "${stage}" \
  --transcript "${evidence}/fumagician-transcript.log" \
  --answer-continue "${answer}"
driver_rc=$?
set -e
sleep 2

root nvme fw-log /dev/nvme0 >"${evidence}/fw-log-after.txt" || true
root nvme id-ctrl /dev/nvme0 | grep -E '^(sn|mn|fr|frmw|fwug) ' >"${evidence}/id-ctrl-after.txt" || true
root nvme smart-log /dev/nvme0 -o json >"${evidence}/smart-after.json" || true
cat /sys/bus/pci/devices/${expected_bdf}/aer_dev_correctable >"${evidence}/aer-endpoint-after.txt"
cat /sys/bus/pci/devices/${expected_root_port}/aer_dev_correctable >"${evidence}/aer-root-after.txt"
root dmesg -T | grep -iE 'nvme|aer|pcie' | tail -40 >"${evidence}/dmesg-tail.txt" || true
# Prove the installed root filesystem is still readable after the utility.
sha256sum /etc/hostname /etc/os-release >"${evidence}/root-read-check.txt" ||
  fail 'root filesystem read check failed after the utility'
root chown -R "$(id -u):$(id -g)" "${evidence}" || true

jq -n --arg mode "${mode}" --argjson rc "${driver_rc}" \
  --arg before "$(cat "${evidence}/fw-log-before.txt" | tr '\n' ' ')" \
  --arg after "$(cat "${evidence}/fw-log-after.txt" | tr '\n' ' ')" \
  '{status: (if $rc == 0 then "utility-returned-ok" else "utility-failed" end),
    mode: $mode, driver_exit: $rc, fw_log_before: $before, fw_log_after: $after}' \
  >"${evidence}/summary.json"

[[ ${driver_rc} -eq 0 ]] || fail "Samsung utility driver exited ${driver_rc}; see ${evidence}"

if [[ ${mode} == vendor-dry-run ]]; then
  printf '%s\n' 'VENDOR DRY RUN complete: the utility detected the drive and was told N.'
  exit 0
fi
printf '%s\n' \
  'Samsung utility reported completion. The new image activates at the next' \
  'controller reset: fully power off (not reboot), reseat/inspect the SSD, then' \
  "cold boot and verify ${expected_new_firmware}, SMART, Gen4 x4, and the" \
  'idle/bounded-read clearance before any GPU work. Swap remains off.'
