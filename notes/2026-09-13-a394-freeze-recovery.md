# A394 recovery and teardown qualification, 2026-09-13

A394's eight depth rows survived the host interruption. Direct comparison of the
external `depth-ladder.json` files for A382 and A394 confirms two passed rows
at each of 2K/8K/16K/32K, identical output hashes across both servers, and a
maximum matched-row rate difference of 0.066 tok/s. The restored tracked A394
JSON equals its external raw summary. These remain lab depth measurements,
not a new class-balanced record or certified long-context battery.

## Teardown and freeze evidence

The A394 supervisor saved `final.rc=143` and child rc 143. Its server log reports
workers exited gracefully at 14:32:37 EDT, followed by forced EngineCore
termination at 14:32:39. The saved listener snapshot lacks port 20011.
The supervisor's GPU postflight uses cached receipts, not fresh device-health
measurements. Do not describe this as an independently verified clean teardown.

The previous boot (`add6faa607fb4dbaa027b1b40a4bcc8f`) journal ends at
2026-09-13 14:32:40 EDT with swap being re-enabled. Current boot
`d68920e0d0d943b8808314e0445f8960` began at 15:47:45 EDT. Timing associates the
interruption with teardown/restoration; it does not establish swap, GPU, or
storage as the cause. The final pressure sample had 126,937,124 KiB available,
zero swap, zero corrected NVMe/root AER counters; minimum available memory was
8,105,592 KiB (the earlier note's ~8.11 uses millions of KiB, not decimal GB).

Hold further Flash-Next launches pending a bounded review of host restoration
and teardown. The cached xpu-smi bypass and five-minute spacing did not establish
freeze prevention. Do not add active GPU polling, swap toggles, cache drops,
driver resets or an automatic reboot as a diagnostic shortcut.

## Recovery

Claude's A394 commit `83f08c6b6b2b5850bb473c6ac8373ccff4ca0237` was already
on GitHub. Thirteen empty loose Git objects were restored from an exact remote
commit object store; the empty result note and JSON were restored from that
commit. Damaged metadata, empty files, the pre-existing family diff and passive
host evidence are retained at
`/home/steve/identified-mistakes/recovery-20260913-a394/`.
Main was fast-forwarded to the newer remote main without replacing unrelated
work. This is bounded recovery, not a full disk or repository integrity audit.

No model or GPU probe was launched. Docker was empty and host memory plentiful.
The Corsair evidence volume was mounted read-only by UUID
`4E0E66ED0E66CD91` at `/mnt/usb-models`; the RAID volume remains unmounted.
