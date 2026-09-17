# Idle host freeze, 2026-09-17 ~15:55 UTC (boot 6701dad4)

## Timeline (journal, boot -2 of the 23:51 UTC boot)

| UTC | Event |
| --- | --- |
| 13:55 | Boot (kernel 7.0.0-31-generic, GuC 70.72.1) after the previous freeze |
| 14:16 | Server 74b segfaults (sampler load race); kernel logs CAT error + engine reset + devcoredump on 0000:43:00.0; last XPU process exits |
| 14:23 | Packet 76 launch refused by the sealed launcher (fault in boot journal); no XPU process from here on |
| 15:19 | Kernel deletes the expired devcoredump (benign) |
| 15:45 | Heartbeat: load 0.03, no D-state tasks, runtime PM pinned on |
| 15:55:01 | Last journal line (sysstat cron); host silent afterwards: **freeze with zero GPU processes** |
| 23:45 | User resets; a 50 s boot (a33dbe55), then the current boot 23:51 UTC, again kernel -31 |

## Reading

Four freezes today, this one with no LTX process for 99 minutes and load near
zero. The workload is not the trigger. Runtime PM was verified pinned on all
four cards eleven minutes before the last journal line, so the earlier
runtime-suspend race is not the cause either. What remains is the platform:
kernel 7.0.0-31 (installed 09-05, the closest correlate) and the manual
GuC 70.72.1 "testing-only" blob. No kdump/pstore is configured, so there is
still no backtrace.

## Action (user's call; nothing here reboots)

Set the next boot to kernel 7.0.0-30 (one variable at a time; GuC restore
second): the `grub-reboot` line is given in the status update; it only takes
effect at the next reboot. Then kdump with `kernel.hardlockup_panic=1`.
Packet 76 runs meanwhile as this boot's single server.
