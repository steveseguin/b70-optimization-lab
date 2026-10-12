# Packet 34 K0 preflight refusal, 2026-10-12

Coordinator decision: **retired on 2026-10-12: preflight refusal on old reviewed lines; no process started; no device contact**.

K0 was attempted on card 3 at 2026-10-12 02:23:55 UTC. The initial kernel
journal scan included old engine-reset and device-coredump lines from this boot.
The owner reviewed those incidents on October 11 and authorized continued GPU
work; the coordinator reports about forty clean packet 17–33 windows since.
The refusal did not report a new incident.

The original boot latch and the complete `build/k0-r34` directory were moved
here byte-for-byte, including three original trailing spaces in the kernel log.
`SHA256SUMS` verifies those original bytes. The refused
`window.json` records `device_executed=false`, with no PID or command; the
latch has `pid=null`. The original hash-bound build receipt is also retained.
There is no active packet 34 latch left from this refusal. No device coredump
was touched and no native process was launched by this repair.

The revised [window instructions](../../WINDOW.md) require the coordinator's
explicit review boundary, `2026-10-12T02:20:00Z`, for new `k0-r34b` / `r1-r34b`
outputs. This boundary admits only reviewed history: any newer fault still
latches, and an existing genuine packet 34 latch is never bypassed.
