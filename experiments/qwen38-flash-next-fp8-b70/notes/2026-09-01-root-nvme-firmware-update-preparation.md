# Qwen3.8 Flash-Next root-NVMe firmware-update preparation

Date: 2026-09-01
Status: recovery artifacts and a modern live fallback are verified; no firmware
write occurred and GPU execution remains blocked

## Live hardware state

The fresh installed-OS boot did not clear the Samsung endpoint. With no model,
server, or GPU process running, `0000:01:00.0` rose from 34 to 79 corrected
events and retained one corrected `NonFatalErr`; the root-port counter remained
zero. Firmware is still `4B2QGXA7`. SMART remains clean (`critical_warning=0`,
zero media errors, zero NVMe error-log entries) and temperature stayed
41--42 C. This is further evidence for the SSD endpoint/link path rather than
Qwen arithmetic, B70 operation, NAND failure, or overheating.

## Verified recovery artifacts

The external recovery root is:

`/mnt/usb-models/pre-firmware-backup-20260901`

Its accepted set contains complete, restore-tested bundles for the lab repo,
vLLM overlay, vLLM-XPU-kernels overlay, and nested oneDNN source. The accepted
checksums and exact post-commit lab head live in `SHA256SUMS.accepted` and
`RECOVERY-MANIFEST.md` inside that external recovery root. Their own hashes are
deliberately not embedded here: doing so would make the tracked commit and its
bundle recursively change one another. The external manifest is refreshed and
restore-tested after the tracked preparation commit.

The first two kernel bundles were rejected despite `git bundle verify`
reporting them complete. The working kernel repository is a blobless partial
clone, and an empty restore exposed a missing prerequisite object. A new bundle
was reconstructed through a fresh full upstream mirror, fetched into an empty
repository at exact lab head
`e421889999bc1e5a5f11044d14548b9afdba644d`, and passed strict full-object
verification with lazy fetching disabled. The rejected artifacts remain
clearly labeled and are excluded from `SHA256SUMS.accepted`. These are verified
lab/code recovery artifacts, not a sector-for-sector image of the root disk.

## Vendor updater and boot-media results

Samsung's official 980 PRO `5B2QGXA7` ISO remains preserved at:

`/mnt/usb-models/tools/samsung-980-pro-firmware/Samsung_SSD_980_PRO_5B2QGXA7.iso`

Its SHA-256 is
`4c02f7b5641c2b6ab6f0b43686f80b303a50a33e0da1abc6465c1ba6d2dc6e1c`.
The original vendor ISO was written and read back on the 8-GB USB, but the user
reported that selecting it in UEFI hung before the updater UI. Its bundled
Linux kernel is `4.5.3`, so platform compatibility is the leading inference,
not a proven firmware-update failure. No update selection or firmware commit
occurred. Temporary UEFI entries were removed and the exact original boot order
was restored: `0002,0003,0004,0005,0006,0001`.

The official payload was audited without choosing a raw image. Its metadata
explicitly allows `4B2QGXA7 -> 5B2QGXA7`, but contains two distinct 2-MiB
images. Samsung's updater owns additional image-selection logic; direct
`nvme fw-download`, guessing one image, or concatenating them is prohibited.

The vendor-supported preference is current Samsung Magician on Windows while
the SSD remains directly attached to an internal M.2 slot. Because no supported
Windows environment is prepared here, a modern-live fallback is ready:

- Ubuntu `24.04.4` desktop ISO, 6,655,619,072 bytes;
- official SHA-256 and full raw-USB readback SHA-256:
  `3a4c9877b483ab46d7c3fbe165a0db275e1ae3cfe56a5657e5a47c2f99a99d1e`;
- USB identity: `/dev/sdc`, `USB Flash Disk`, 8,022,654,976 bytes;
- verified live marker:
  `Ubuntu 24.04.4 LTS "Noble Numbat" - Release amd64 (20260210)`;
- verified UEFI loader: `EFI/boot/bootx64.efi`;
- live ISO9660 identity: 6,650,044,416 bytes, label
  `Ubuntu 24.04.4 LTS amd64`, UUID `2026-02-10-01-39-48-00`;
- exact SHA-256 binding for `.disk/info`, `md5sum.txt`, `casper/vmlinuz`,
  `casper/initrd`, and `EFI/boot/bootx64.efi`;
- untouched official updater pack on the Corsair external drive:
  `/mnt/usb-models/tools/samsung-980-pro-firmware/live-updater`;
- pack archive SHA-256:
  `4080184e2d87bf29ff6ed5c8d2d5bbb3a49025749618a98af32f429ef7ef676e`.

The repo-tracked/external helper SHA-256 is
`b88c038d004de9273f140237582d8db3f972d1da530758bb2d979784e1f981c4`.
It refuses the installed OS; the wrong live-media size, label, UUID, release
manifest, kernel, initrd, or UEFI loader; altered/staged updater bytes; a
different SSD or firmware; another Samsung drive; unreadable identities;
mounted target descendants; any active swap; or failed inspection commands.
It rechecks state immediately before starting Samsung's untouched utility. It
never selects a drive or raw image and never reboots automatically. The two
prior archives remain preserved with `superseded-57a20681301d` and
`superseded-0d1258ad012b` suffixes; they are historical evidence, not the
current live fallback.

## Remaining maintenance boundary

Do not boot the live updater and write firmware across the presently noisy link
without first fully powering off and reseating/inspecting the SSD, heatsink,
thermal pad, M.2 connector, and standoff. After reseat, use Windows Magician if
available; otherwise boot the verified Ubuntu USB, choose **Try Ubuntu**, and
follow `live-updater/README.md`. Keep stable power and select only serial
`S6WSNS0T109768K` in Samsung's UI.

After the utility finishes, fully power off again, cold boot, verify
`5B2QGXA7`, SMART, and Gen4 x4, then generate a boot- and serial-bound clearance
receipt only after 30 minutes idle plus a bounded read with zero endpoint and
root-port corrected-event delta. Until that receipt validates, no Qwen GPU
component or full-model work is authorized.
