# Userspace memory test, 2026-09-20 (boot 8f469374)

**Result: PASS.** Four parallel `memtester 16G 1` workers (Ubuntu memtester
4.6.0, mlock shimmed — RLIMIT_MEMLOCK is unprivileged) covered 64 GB of the
125 GB host RAM with the full battery (stuck address, random value, compare
XOR/SUB/MUL/DIV/OR/AND, sequential increment, solid bits, block sequential,
checkerboard, bit spread, bit flip, walking ones/zeroes). One full pass,
~1 h 32 m, zero failures on every worker.

Scope limits: userspace pages only (the kernel's own pages and the ~59 GB not
allocated are untested); pages were not locked, though with 121 GB free there
is no pressure to migrate them. This materially weakens but does not close the
bad-DIMM hypothesis for the three campaign freezes and the historical byte
corruptions — memtest86+ (installed in /boot, needs a console reboot) remains
the definitive test and stays on the user's list, as do BIOS Power Supply
Idle Control and the PSU rating check.
