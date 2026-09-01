# Qwen3.8 Flash-Next FP8 A46 host-freeze interruption

Date: 2026-09-01
Status: preserved healthy-endpoint, zero-request host interruption

A46 passed artifact and four-card preflight, loaded all 131 local-NVMe shards
in 78.4 seconds, placed the exact 11.92 GiB PLE shard in host memory on each
rank, completed the size-1 full-decode graph capture, emitted one nonempty
Torch trace for each rank, and became healthy. The client never started and no
inference request was sent. The host then became unresponsive and was hard
restarted. A46 therefore has no quality or performance credit.

The last system-accounting sample at 04:30:05 reported 36,421,640 KiB
available memory and 7,042,704 KiB swap in use, with active reclaim and swap
traffic. The prior-boot journal ends at that sample without an orderly
shutdown, OOM, B70 reset, kernel panic, or fatal NVMe command error. The
application log continued through endpoint health at 04:30:53, so the exact
time and cause of the later host lockup are not proven.

Three hardware-corrected PCIe physical-layer receive reports named the local
Samsung 980 PRO controller during the A46 window. Post-restart NVMe SMART is
otherwise clean: 0 media errors, 0 error-log entries, 33 C, and 4% life used.
The drive runs firmware `4B2QGXA7`; Samsung currently publishes
`5B2QGXA7` for the 980 PRO series. Firmware maintenance is a separate,
backup-first maintenance action and is not performed inside this model arm.

The next boot reports AMD reset reason `0x00010800` (`BP_SYS_RST_L` reset-pin
assertion), unlike the `0x00080800` software-reset reason recorded for clean
Codex-initiated reboots. This rules out an ordinary OS/Codex reboot but cannot
distinguish a manual reset from board or firmware logic.

The next attempt must retain A46 inference and quality identity while reducing
host lockup risk: disable disk-backed swap for the bounded load, select the
runtime PCIe ASPM performance policy, continuously record memory/reclaim/I/O
state, and fail closed before inference if those controls are not exact. These
are host-load controls, not model-speed selectors. No reboot or per-boot load
rule applies.
