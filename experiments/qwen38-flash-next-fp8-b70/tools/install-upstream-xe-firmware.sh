#!/usr/bin/env bash
# Install the upstream linux-firmware Battlemage GuC (xe/bmg_guc_70.bin) in
# place of Ubuntu's 70.44.1, which the xe driver in kernel 7.0.0-30 flags
# every boot ("GuC firmware (70.54.0) is recommended"). Ubuntu's pending
# linux-firmware 0ubuntu2.29 ships the byte-identical 70.44.1 file, so the
# package route cannot fix it.
#
# Modes:
#   --dry-run    (default) verify the staged upstream file, show what would change
#   --install    back up the current .zst, install the upstream file zstd-compressed,
#                refresh the initramfs, and print the post-install state
#   --reload-xe  after --install: with no GPU users, unbind the four B70s, unload
#                and reload the xe module so the new GuC loads without a reboot
#
# Only the GuC file changes; HuC stays as shipped. Everything is reversible:
# the backup directory holds the original file and `--restore` puts it back.
set -Eeuo pipefail

upstream=/mnt/usb-models/tools/intel-xe-firmware/bmg_guc_70.bin.upstream
expected_upstream_sha=de81c75f46a127c33cd59f604d800e9ffc7ed3495967ba0d8767cd6985ab398b
expected_installed_sha=b95b0d1892ed1f271c71
target=/lib/firmware/xe/bmg_guc_70.bin.zst
backup_dir=/lib/firmware/xe/backup-ubuntu-70.44.1
sudo_password_file=/home/steve/SUDOPASSWORD.txt
b70s=(0000:23:00.0 0000:27:00.0 0000:43:00.0 0000:47:00.0)

fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
root() { sudo -S -p '' "$@" <"${sudo_password_file}"; }
mode=${1:---dry-run}

[[ ${EUID} -ne 0 ]] || fail 'run as the ordinary user; privileged steps use sudo'
[[ -f ${upstream} ]] || fail "staged upstream file missing: ${upstream}"
[[ $(sha256sum "${upstream}" | cut -d' ' -f1) == "${expected_upstream_sha}" ]] || fail 'upstream GuC hash drifted'
python3 - "${upstream}" <<'PY' || fail 'upstream file does not embed GuC 70.72.1'
import struct, sys, pathlib
b = pathlib.Path(sys.argv[1]).read_bytes()[:0x200]
sys.exit(0 if struct.pack('<I', (70 << 16) | (72 << 8) | 1) in b else 1)
PY
[[ $(sha256sum "${target}" | cut -c1-20) == "${expected_installed_sha}" || -f ${backup_dir}/bmg_guc_70.bin.zst ]] ||
  fail 'installed GuC file is neither the known Ubuntu 70.44.1 nor already backed up'

case "${mode}" in
  --dry-run)
    printf 'dry-run: would back up %s to %s and install upstream GuC 70.72.1 (%s)\n' "${target}" "${backup_dir}" "${expected_upstream_sha:0:12}"
    dmesg_line=$(root dmesg | grep -m1 'GuC firmware from xe/bmg_guc_70.bin' || true)
    printf 'current: %s\n' "${dmesg_line#*] }"
    printf 'xe refcnt=%s render nodes=%s\n' "$(cat /sys/module/xe/refcnt)" "$(ls /dev/dri | grep -c renderD)"
    ;;
  --install)
    root mkdir -p "${backup_dir}"
    [[ -f ${backup_dir}/bmg_guc_70.bin.zst ]] || root cp -a "${target}" "${backup_dir}/bmg_guc_70.bin.zst"
    tmp=$(mktemp /tmp/bmg_guc_70.XXXXXX.zst)
    zstd -q -19 -f "${upstream}" -o "${tmp}"
    [[ $(zstdcat "${tmp}" | sha256sum | cut -d' ' -f1) == "${expected_upstream_sha}" ]] || fail 'compressed copy does not round-trip'
    root install -o root -g root -m 0644 "${tmp}" "${target}"
    rm -f "${tmp}"
    [[ $(zstdcat "${target}" | sha256sum | cut -d' ' -f1) == "${expected_upstream_sha}" ]] || fail 'installed file mismatch'
    root update-initramfs -u >/dev/null 2>&1 || fail 'update-initramfs failed'
    printf 'installed upstream GuC 70.72.1 at %s (backup in %s); takes effect on xe reload or reboot\n' "${target}" "${backup_dir}"
    ;;
  --restore)
    [[ -f ${backup_dir}/bmg_guc_70.bin.zst ]] || fail 'no backup to restore'
    root install -o root -g root -m 0644 "${backup_dir}/bmg_guc_70.bin.zst" "${target}"
    root update-initramfs -u >/dev/null 2>&1 || true
    printf 'restored Ubuntu 70.44.1 GuC file\n'
    ;;
  --reload-xe)
    [[ $(zstdcat "${target}" | sha256sum | cut -d' ' -f1) == "${expected_upstream_sha}" ]] || fail 'run --install first'
    if fuser -s /dev/dri/renderD* 2>/dev/null; then fail 'a process holds a B70 render node'; fi
    pgrep -f 'vllm serve|xpu-graph-gate|xpu-smi' >/dev/null && fail 'GPU runtime processes are present'
    # `root` feeds the sudo password on stdin, so the address must be passed as
    # an argument, never piped: a piped `tee` would receive the password instead.
    for bdf in "${b70s[@]}"; do
      [[ -e /sys/bus/pci/drivers/xe/${bdf} ]] && root bash -c "echo ${bdf} > /sys/bus/pci/drivers/xe/unbind"
    done
    sleep 2
    [[ $(cat /sys/module/xe/refcnt) == 0 ]] || fail "xe refcnt is $(cat /sys/module/xe/refcnt) after unbinding; something else holds the driver"
    sleep 2
    root modprobe -r xe || fail 'xe module unload failed (refcnt still held)'
    root modprobe xe || fail 'xe module reload failed'
    for _ in $(seq 1 30); do
      [[ $(ls /dev/dri 2>/dev/null | grep -c renderD) == 4 ]] && break
      sleep 1
    done
    [[ $(ls /dev/dri | grep -c renderD) == 4 ]] || fail 'four render nodes did not return'
    root dmesg | grep 'GuC firmware' | tail -4
    # `grep -q` exits on the first match and the SIGPIPE'd dmesg then fails the
    # pipeline under pipefail, which reported a false FAIL on 2026-09-03; let grep
    # read the whole buffer instead.
    [[ -n $(root dmesg | grep 'version 70.72.1') ]] || fail 'reloaded driver did not report GuC 70.72.1'
    printf 'xe reloaded with GuC 70.72.1 on four B70s\n'
    ;;
  *) fail 'usage: --dry-run | --install | --reload-xe | --restore' ;;
esac
