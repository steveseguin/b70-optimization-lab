#!/usr/bin/env bash
set -Eeuo pipefail

expected_serial=S6WSNS0T109768K
expected_model='Samsung SSD 980 PRO with Heatsink 1TB'
expected_old_firmware=4B2QGXA7
expected_new_firmware=5B2QGXA7
expected_binary_sha=a268c44020a1226df198237c16f315dc9e7dd120186021ac430118dac4cd9153
expected_dsrd_sha=ba85e97c70f1f8c3f6abafcda7c9ba977bcad75f3ea2e9913ff98f69c9ba3c7c
expected_payload_sha=9ecee639ce2c8d34cb8ba13cd2d2a4955e094100394dba1c59ed44b29584a85e
expected_cdrom_bytes=6650044416
expected_cdrom_label='Ubuntu 24.04.4 LTS amd64'
expected_cdrom_uuid=2026-02-10-01-39-48-00
expected_info_sha=fa8c36e43a506028cfa47202d5ea5d172b3f1a3512e89461692f99adb7e90d85
expected_manifest_sha=3e499c309ef90c804ab4aaee5ded5eb02331cc6078ce27c697ed6fced73c1c8f
expected_vmlinuz_sha=d3f1cc6693d93fcf6663cd1e04d31031f41e8abd0c14b0ca953ef524a62e4489
expected_initrd_sha=b5dd55a35ccb0e43f597531f8c5fc27bf10169bbf675c4ac902980667f493f50
expected_bootx64_sha=6fe6e1bcbe6cf6baec8e056d40361ca1aa715cc04ddcc2855351de060b84350b

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

[[ ${EUID} -ne 0 ]] || fail 'run this helper as the live user, not as root'

root_source=$(findmnt -nro SOURCE /)
root_fstype=$(findmnt -nro FSTYPE /)
case "${root_source}:${root_fstype}" in
  overlay:overlay | overlay:overlayfs | /cow:overlay | /cow:overlayfs) ;;
  *)
    fail "root is ${root_source}:${root_fstype}; boot a modern live environment first"
    ;;
esac
cmdline=$(< /proc/cmdline)
[[ " ${cmdline} " == *' boot=casper '* ]] ||
  fail 'kernel command line does not identify an Ubuntu casper live boot'
[[ -r /cdrom/.disk/info && -d /cdrom/casper ]] ||
  fail 'expected Ubuntu live-media markers are absent under /cdrom'
read -r cdrom_source cdrom_fstype cdrom_options < <(
  findmnt -nro SOURCE,FSTYPE,OPTIONS --target /cdrom
)
[[ -b ${cdrom_source} && ${cdrom_fstype} == iso9660 && ",${cdrom_options}," == *,ro,* ]] ||
  fail 'the live medium is not a read-only ISO9660 block device'
cdrom_bytes=$(lsblk -dnbo SIZE "${cdrom_source}")
cdrom_label=$(lsblk -dno LABEL "${cdrom_source}")
cdrom_uuid=$(lsblk -dnro UUID "${cdrom_source}")
[[ ${cdrom_bytes} == "${expected_cdrom_bytes}" && \
   ${cdrom_label} == "${expected_cdrom_label}" && \
   ${cdrom_uuid} == "${expected_cdrom_uuid}" ]] ||
  fail 'the live-medium size, label, or UUID does not match the prepared image'

require_media_hash() {
  local relative=$1 expected=$2
  local path=/cdrom/${relative}
  [[ -f ${path} && ! -L ${path} ]] || fail "live-medium file is missing or linked: ${relative}"
  [[ $(sha256sum "${path}" | cut -d' ' -f1) == "${expected}" ]] ||
    fail "live-medium file hash mismatch: ${relative}"
}

require_media_hash .disk/info "${expected_info_sha}"
require_media_hash md5sum.txt "${expected_manifest_sha}"
require_media_hash casper/vmlinuz "${expected_vmlinuz_sha}"
require_media_hash casper/initrd "${expected_initrd_sha}"
require_media_hash EFI/boot/bootx64.efi "${expected_bootx64_sha}"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for name in fumagician DSRD.enc 5B2QGXA7.enc; do
  [[ -f ${script_dir}/${name} ]] || fail "missing ${script_dir}/${name}"
done

[[ $(sha256sum "${script_dir}/fumagician" | cut -d' ' -f1) == "${expected_binary_sha}" ]] ||
  fail 'Samsung utility hash mismatch'
[[ $(sha256sum "${script_dir}/DSRD.enc" | cut -d' ' -f1) == "${expected_dsrd_sha}" ]] ||
  fail 'Samsung DSRD hash mismatch'
[[ $(sha256sum "${script_dir}/5B2QGXA7.enc" | cut -d' ' -f1) == "${expected_payload_sha}" ]] ||
  fail 'Samsung firmware payload hash mismatch'

target_controller=
target_model=
target_firmware=

verify_target_state() {
  local controller_path controller model serial firmware block_path
  local device mountpoints vendor other_model other_serial lsblk_output swap_output

  target_controller=
  for controller_path in /sys/class/nvme/nvme*; do
    [[ -r ${controller_path}/serial && -r ${controller_path}/model ]] ||
      fail "cannot read NVMe identity: ${controller_path}"
    serial=$(tr -d '[:space:]' <"${controller_path}/serial")
    model=$(sed 's/[[:space:]]*$//' "${controller_path}/model")
    if [[ ${model,,} == *samsung* && ${serial} != "${expected_serial}" ]]; then
      fail "another Samsung NVMe is present: ${model} serial ${serial}"
    fi
    if [[ ${serial} == "${expected_serial}" ]]; then
      target_controller=${controller_path##*/}
      target_model=${model}
      target_firmware=$(tr -d '[:space:]' <"${controller_path}/firmware_rev")
    fi
  done
  [[ -n ${target_controller} ]] || fail "target serial ${expected_serial} is absent"
  [[ ${target_model} == "${expected_model}" ]] ||
    fail "unexpected target model: ${target_model}"
  [[ ${target_firmware} == "${expected_old_firmware}" ]] ||
    fail "expected ${expected_old_firmware}, found ${target_firmware}"

  for block_path in /sys/block/sd*; do
    [[ -r ${block_path}/device/vendor && -r ${block_path}/device/model ]] ||
      fail "cannot read block-device identity: ${block_path}"
    vendor=$(sed 's/[[:space:]]*$//' "${block_path}/device/vendor")
    other_model=$(sed 's/[[:space:]]*$//' "${block_path}/device/model")
    other_serial=$(sed 's/[[:space:]]*$//' "${block_path}/device/serial" 2>/dev/null || true)
    if [[ ${vendor,,}:${other_model,,} == *samsung* ]]; then
      fail "another Samsung block device is present: ${block_path##*/} ${vendor} ${other_model} ${other_serial}"
    fi
  done

  block_path=/dev/${target_controller}n1
  [[ -b ${block_path} ]] || fail "expected namespace ${block_path} is absent"
  if ! lsblk_output=$(lsblk -nrpo NAME,MOUNTPOINTS "${block_path}"); then
    fail "cannot inspect target descendants with lsblk: ${block_path}"
  fi
  [[ -n ${lsblk_output} ]] || fail "lsblk returned no target descendants: ${block_path}"
  while read -r device mountpoints; do
    [[ -z ${mountpoints} ]] || fail "target descendant is mounted: ${device} ${mountpoints}"
  done <<<"${lsblk_output}"

  if ! swap_output=$(swapon --show=NAME --noheadings 2>&1); then
    fail "cannot inspect active swap: ${swap_output}"
  fi
  if [[ -n ${swap_output//[[:space:]]/} ]]; then
    fail 'active swap is not allowed during the live firmware update'
  fi
}

verify_target_state

printf '%s\n' \
  'Samsung 980 PRO firmware update live gate passed.' \
  "Target: ${target_model}" \
  "Serial: ${expected_serial}" \
  "Current firmware: ${expected_old_firmware}" \
  "Required firmware: ${expected_new_firmware}" \
  '' \
  'The official Samsung utility will open next. Select only the drive with' \
  "serial ${expected_serial}, keep stable power, and do not interrupt it."

confirmation=
read -r -p "Type UPDATE-${expected_serial}-TO-${expected_new_firmware}: " confirmation
[[ ${confirmation} == "UPDATE-${expected_serial}-TO-${expected_new_firmware}" ]] ||
  fail 'confirmation did not match'

stage=$(mktemp -d /tmp/samsung-980-pro-fw.XXXXXX)
trap 'sudo rm -rf -- "${stage}" 2>/dev/null || true' EXIT

sudo -v
verify_target_state
sudo chown root:root "${stage}"
sudo chmod 0755 "${stage}"
sudo install -o root -g root -m 0555 "${script_dir}/fumagician" "${stage}/fumagician"
sudo install -o root -g root -m 0444 "${script_dir}/DSRD.enc" "${stage}/DSRD.enc"
sudo install -o root -g root -m 0444 "${script_dir}/5B2QGXA7.enc" "${stage}/5B2QGXA7.enc"
[[ $(sha256sum "${stage}/fumagician" | cut -d' ' -f1) == "${expected_binary_sha}" ]] ||
  fail 'staged Samsung utility hash mismatch'
[[ $(sha256sum "${stage}/DSRD.enc" | cut -d' ' -f1) == "${expected_dsrd_sha}" ]] ||
  fail 'staged Samsung DSRD hash mismatch'
[[ $(sha256sum "${stage}/5B2QGXA7.enc" | cut -d' ' -f1) == "${expected_payload_sha}" ]] ||
  fail 'staged Samsung firmware payload hash mismatch'
verify_target_state
(
  cd -- "${stage}"
  sudo ./fumagician
)

printf '%s\n' \
  'Samsung utility returned.' \
  'Do not start the installed OS workload yet.' \
  'Fully power off, then cold boot and verify firmware, SMART, PCIe link, and' \
  'a zero-error idle/read clearance before any GPU experiment.'
