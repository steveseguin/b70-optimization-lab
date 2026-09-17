# Firmware and kernel review for the silent lockups (2026-09-17)

Requested by the user after the ninth reboot in two days. The lockups are
independent of the LTX workload (two idle-boot freezes on 09-17 alone with
nothing running, see the incident note); they need a platform-level change.

## What is installed, and what the evidence says

| Component | State on this host | Evidence |
| --- | --- | --- |
| Kernel | **7.0.0-31-generic** since 2026-09-05; 7.0.0-30 still installed | apt history; `/boot/vmlinuz-7.0.0-30-generic` present |
| xe GuC firmware | **70.72.1**, a manual replacement of the Ubuntu package file | `dpkg --verify linux-firmware` flags `xe/bmg_guc_70.bin.zst` as modified; the package's own blob (April 15 build, 70.44.1) is preserved in `/lib/firmware/xe/backup-ubuntu-70.44.1/` |
| Upstream status of 70.72.1 | posted to drm/xe on 2026-07-28 as **"for testing only"** (mmp_ver 70.72.1, UAPI 1.38.1); the last upstream *recommendation* for Battlemage in the series is **70.65.0** (2026-07-14, drm-xe-next), before that 70.60.0 (April), 70.58.0, 70.55.3 | intel-xe list archives |
| When 70.72.1 arrived here | already running on 2026-09-02 with kernel 7.0.0-30 (Qwen-lane replay note); reinstalled 2026-09-03 after an A/B against 70.44.1 that found no launch-latency difference | `experiments/qwen38-27b-b70/notes/2026-09-02-qwen38-fp8-r139-four-b70-host-replay.md` |
| First documented silent lockups | 2026-09-05 (Qwen lane), 2026-09-14 onward (this lane) | memory and lane notes |

So the timeline is: 70.72.1 in use by early September on kernel -30 without
documented lockups; kernel -31 on 09-05; lockups from 09-05. The kernel
upgrade is the closest correlate. The firmware is a secondary suspect: it is
a testing-only blob, newer than anything the 7.0 kernel was validated with.

## Recommendation, in order (each needs a reboot; the user decides)

1. **Boot kernel 7.0.0-30** from the GRUB "Advanced options" menu. No file
   changes; the 09-02 replay ran on exactly this combination. Leave the box
   idle for an hour; four of the lockups happened idle within 5–17 minutes
   of boot, so that is a real test.
2. If it still locks up, **restore the package GuC 70.44.1**:
   `sudo cp /lib/firmware/xe/backup-ubuntu-70.44.1/bmg_guc_70.bin.zst /lib/firmware/xe/bmg_guc_70.bin.zst && sudo update-initramfs -u`
   then reboot. (`dpkg --verify` will then be clean.) A middle option is
   upstream's last recommended 70.65.0, but no copy of it is on this host.
3. Either way, make the next lockup leave evidence: install `linux-crashdump`,
   set `kernel.hardlockup_panic=1` and `kernel.panic=30`, reboot once. Today
   every lockup ends in a manual power cycle with nothing on disk.

Not recommended: newer firmware. The chain of upstream postings shows
70.72.1 is the newest thing tested for Battlemage; there is no "better"
firmware forward of it, only the validated older ones behind it.
