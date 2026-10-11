# Packet 26 K1a attempt a (card 0): clean refusal, "expanded dense geometry" (2026-10-11 21:18 UTC)

K0 passed on cards 0 and 2. K1a stopped after 21 s with a clean exit, complete teardown
and a clean kernel log: the GEMV fixture half threw `expanded dense geometry`, the
argument check at `stage2/packet10-kopt5/kernels.cpp:45` (expanded dense GEMV: split 1
or 4, one expert, count 1, no routes or status, span equal to rows, F16 or BF16
activation). No timing or exactness rows were produced. The check lives in a
device-only source file, so the CPU gates never executed it.
