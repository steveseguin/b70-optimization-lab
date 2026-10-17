# Packet48b: production-context GEMV reconciliation

Packet48 used the right shapes and formats, but not a matched full-layer
control. **No packet48 kernel is production-qualified by this CPU review.**
The large down gain is the strongest candidate; weak gate gains do not justify
assuming that all compact layouts help.

[Reconciliation evidence](reconciliation.json) binds the original timings and
sources. [Preregistration](PREREGISTRATION.md) fixes the complete-layer screen;
[coordinator commands](WINDOW.md) provide its exactness and timing windows.
The production current arm is the actual packet45 Engine, not a reimplementation
of its lane wrapper. The candidate uses packet48's exact-order arithmetic with
the same full-layer fixture, input changes, warmups and timing scope.

Build and evidence symlinks point to
`/home/steve/own-xpu-runtime-results/packet48b-production/`. CPU preparation
never opens a device or model payload. The device coordinator must run E1/E2
and T1/T2 before any performance choice is adopted.

CPU preparation is complete: host and device-program compilation pass; two
fresh host fixture processes each pass **1,824** producer/state comparisons
with the same complete identity; all eight coordinator checks pass. The seal
and its external-artifact admission validate. No device binary ran.
The lean build/evidence tree occupies about 54 MiB. An initial expert-dimension
mistake was caught on CPU and is retained in the
[repair closeout](GEOMETRY-REPAIR-CLOSEOUT.md).
