# Qwen3.8 Flash-Next root-NVMe: in-place firmware path and clearance generator

Date: 2026-09-01 (evening handoff to Claude)
Status: tooling prepared and CPU/pty-tested; no firmware write, no reboot, no
GPU work; GPU execution remains blocked by the root-NVMe link clearance

## Live state at handoff

- `0000:01:00.0` Samsung 980 PRO `4B2QGXA7`, PCIe 16 GT/s x4, ASPM disabled.
- Corrected `RxErr` (physical layer, receiver) on the endpoint about once every
  30 s while idle: sysfs `TOTAL_ERR_COR` 131 at 2h11m uptime, 144 by 2h25m.
  Root port `0000:00:03.1` stays at zero. Reported firmware-first via APEI/GHES.
- SMART clean: `critical_warning=0`, `media_errors=0`, `num_err_log_entries=0`,
  40 C, 4% used, 60 power cycles, 23 unsafe shutdowns.
- `nvme id-ctrl`: `frmw=0x16` (three slots, slot 1 writable, activation
  without reset advertised), `fw-log afi=0x1`, slot 1 `4B2QGXA7`, nothing
  pending.
- Boot -3 (08:32--09:50) ended without any shutdown record while the endpoint
  was logging `RxErr`; boot -2 and -1 shut down cleanly. This is consistent
  with the earlier freeze notes: a root-NVMe link that stops answering leaves
  no journal on the drive that stopped.
- Board: Supermicro M12SWA-TF, BIOS 2.0b (2022-06-28). Supermicro's current
  BIOS is 2.4a (2025-07-17); a BIOS/AGESA refresh is a second-tier lever if
  reseat plus SSD firmware does not clear the receiver errors.
- LVFS/fwupd: the drive is recognised as updatable ("usable for the duration
  of the update", "needs a reboot after installation") but LVFS carries no
  980 PRO release, so fwupd cannot be the vehicle.

## Why an in-place update is acceptable

Samsung's ISO contains a statically linked x86-64 `fumagician` that issues
ordinary NVMe admin commands (`Firmware Image Download`, `Firmware Commit`)
through the kernel's NVMe ioctl path. The utility owns the two-image selection
logic, so it is still the only sanctioned way to choose the payload; it does
not need the ISO's 4.5.3 kernel that hung on this platform. Running it on the
installed OS is the same operation the live-USB path performs, minus the
separate boot; the new image activates at the next controller reset, which the
required full power-off for the SSD reseat provides. The drive keeps serving
the root filesystem during the download, and a rejected image leaves slot 1
unchanged.

The remaining risks are identical to the live path (power loss mid-commit) plus
one installed-OS-specific risk: if the utility ever issued a controller reset
itself, root I/O would stall. Its strings contain only the NVMe status text
for "activation requires reset", not a reset command, and public reports of
running it on a mounted root drive end with "reboot to activate". The helper
below therefore records the firmware log before and after, checks the root
filesystem is still readable after the utility returns, and leaves swap off.

## Prepared tooling (tracked)

- `tools/run-samsung-980-pro-official-updater-in-place.sh` -- fail-closed
  installed-OS runner. Modes: `--dry-run` (gates and tmpfs staging only),
  `--vendor-dry-run` (starts Samsung's utility, answers `N`; proves detection
  without writing), and `--confirm UPDATE-S6WSNS0T109768K-TO-5B2QGXA7`.
  It binds the exact vendor-file hashes from the external `SHA256SUMS`, the
  serial/model/BDF/firmware, slot state, zero non-fatal/fatal AER history,
  zero root-port corrected events, 16 GT/s link, clean cool SMART, the
  tracked runtime-conflict scan, no render-node users, free memory, swap off,
  and evidence outside the target drive. Vendor files are staged in
  root-owned tmpfs so nothing is read from the drive being flashed while the
  utility runs. Every gate runs again immediately before exec.
- `tools/drive-samsung-fumagician-pty.py` -- answers exactly the utility's
  `continue the firmware update? [Y/N]` (Y once, or N for the vendor dry
  run), `on next device? [Y/N]` (N), and `Press any key` prompts through a
  pseudo-terminal, records a full transcript, and fails closed on silence,
  timeout, or a missing `Firmware Update Completed` banner.
- `tools/generate-q38-root-nvme-link-clearance-v1.py` -- producer for the
  fixed `q38_root_nvme_link_clearance_v1` receipt. It refuses before waiting
  when the live controller identity or firmware is wrong, requires clean
  admission (no render-node users, runtime scan clear, clean SMART), polls the
  endpoint and root-port counters through the 30-minute idle window and stops
  on the first event, performs the bounded O_DIRECT read from the local
  shards, then assembles the receipt and passes it through the tracked
  validator against live identity before writing to the fixed path. Rejected
  receipts are written with a `.rejected-<stamp>` suffix; every run writes a
  `.evidence-<stamp>.json` sidecar.

Verification performed: 21 CPU tests across the generator and the existing
validator, 5 pty-driver tests against a fake utility exercising confirm,
vendor-dry-run, missing completion banner, prompt timeout, and missing binary;
ruff clean. The live generator smoke run refused correctly on `4B2QGXA7` and
wrote its evidence sidecar. The helper's `--dry-run` could not be executed
from the agent session (privileged-tool policy), so its full gate chain is
syntax-checked but not yet exercised; run `--dry-run` manually first.

## Recommended sequence (no live USB)

1. `tools/run-samsung-980-pro-official-updater-in-place.sh --dry-run`
2. `... --vendor-dry-run` (utility must list serial `S6WSNS0T109768K`)
3. `... --confirm UPDATE-S6WSNS0T109768K-TO-5B2QGXA7` with stable power
4. Full power off. Reseat/inspect the SSD, heatsink pad, connector, standoff.
5. Cold boot; confirm `5B2QGXA7`, SMART, Gen4 x4.
6. `tools/generate-q38-root-nvme-link-clearance-v1.py` (about 31 minutes).
7. W13-N32 A2 confirmation, then HC gate-mix and HC combine-norm.

If corrected receiver errors persist on `5B2QGXA7` after reseat, the next
discriminators are a different CPU-attached M.2 slot, BIOS 2.4a, and a Gen3
retrain as a diagnostic only.
