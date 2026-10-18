# Packet58e: cheaper one-card exactness chain

A new copy of frozen packet58d. Native sources, the post-load lifetime repair,
BF16 KV and arithmetic `iq3-p49-split32-v1` are unchanged. Card 0 only.

All six inter-window gaps are 90 seconds. Existing deadlines, cooperative
stop, drains, teardown receipts and kernel fault checks remain in place.
The unchanged work allowances plus gaps total 93 minutes, 14 minutes 20 seconds
less than 58d's schedule. These are planning allowances, not measured runtime.

K1a, K1b, KD, W2m, WS and WS128x hold lane A. Compatible lane-B screens may
run on cards 2+3 if actual available memory passes admission. WS128 holds
lane B before waiting for its current screen to drain, then requires the
original whole-host memory floor. Queued lane-A screens see the active lease.

Exact model windows initially require **85,565,068,816 available bytes**,
including the unchanged **8 GiB reserve**. Every device allocation category
is still charged as possible host backing, including the 18 GB cache and
full BF16 KV. The retained 579,248,128-byte shadow observation is explicitly
incomplete; it never replaces unobserved cache/KV allocations. Each successful
model window must provide a real after-load sample and complete native census
before its successor can use the updated observation. All census allowances
remain; observations never lower the seed.

[Memory accounting](MEMORY.md), [coordinator commands](WINDOW.md),
[CPU build/check commands](CPU-BUILD.md), [CPU closeout](CPU-PREPARATION-CLOSEOUT.md)
and [task note](../../../../notes/2026-10-17-own-runtime-packet58e.md).

CPU preparation is complete; device fit, full-load memory, exactness and speed
remain unmeasured. The shared-host WS128x timing is diagnostic only, not a
second timing qualification. Offline publication refuses without a separately
qualified whole-host repeat. No GPU, service or production coordination state
was opened during preparation. Copied historical evidence keeps its old identity.
