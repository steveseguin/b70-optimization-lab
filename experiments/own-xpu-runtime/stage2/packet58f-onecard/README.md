# Packet58f: isolate the one-card owner before enumeration

Copied from frozen 58e. Native sources, arithmetic `iq3-p49-split32-v1`,
full BF16 KV, memory fence and all memory budgets are unchanged.

58e used only the SYCL selector, just as 58c did. Its new lane admission
sensor exposed extra Xe opens that 58c did not inspect. The lane-pair mask
was imported but never applied. The failed record does not identify the extra
BDF, so enumeration is the supported explanation, not a traced driver call.

The child now gets `NEOReadDebugKeys=1`, exact
`FilterBdfPath=0000:23:00.0`, `ZE_ENABLE_PCI_ID_DEVICE_ORDER=1`,
`ZE_AFFINITY_MASK=0`, and `ONEAPI_DEVICE_SELECTOR=level_zero:0`.
A fresh private HOME and refusal of a cwd `igdrcl.config` prevent debug-file
mask overrides. Passive sysfs checks admit only that card's render node.
Every observed owned Xe FD must still identify that BDF; offending FDs are
now saved. This is driver filtering plus a strict monitor, not an OS sandbox.
CPU checks prove the environment and mapping. Native FD isolation remains
pending; no GPU was opened during preparation.

Lane A remains leased. Compatible lane-B screens may overlap exactness.
The shared teardown permit is acquired only after prelaunch admission.
Before-launch refusal releases this packet's lease without touching a prior
shared record. After successful K1 exit and clean postflight, the device drain
is recorded before CPU summary validation. A failed summary remains failed
and cannot advance the queue. Live owners, failed postflight and uncertain
native exits retain coordination records. Shared drain spacing stays 60 seconds.

Exact model windows still need **85,565,068,816 bytes** available. K1 retains
12 GiB, whole-host WS128 retains 118,308,908,048 bytes, the live reserve stays
8 GiB, and the full 18 GB cache and BF16 KV are charged. All six gaps stay
90 seconds. No arithmetic, safety floor or timing qualification changed.

[Coordinator commands](WINDOW.md), [CPU checks](CPU-BUILD.md),
[mask evidence](evidence/mask-cpu.json), [cause](evidence/mask-root-cause.json),
[closeout](CPU-PREPARATION-CLOSEOUT.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet58f.md).

Start fresh at `evidence/card0-58f-a/K1a`. Older seals cannot supply K1 receipts.
No GPU result, speed claim, external submission or public recipe is established.
