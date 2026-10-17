# Packet54: exact-order compute round

Packet53b's three exact winners are banked at 23.4385/23.4375 microseconds per
ordinary layer. Its own 35-microsecond bar failed. The coordinator asks for
packet49d once the banked total reaches 40 microseconds in both owners.
[Packet53b device closeout](2026-10-17-own-runtime-packet53b.md#device-results--october-17-09450950-utc).

Packet54 targets the remaining compute-heavy work: route, GDN recurrence,
HC injection/mixing/normalization and FFN combine. Source diagnosis found
repeated normalization and deterministic math worth sharing. State is already
held in registers in recurrence; merely changing that label is not a lever.
HC inject stays unchanged because its existing ordered sum offers no large,
clear improvement in this round. The packet46 norm fusion had too few
workgroups and a serial inverse; this round keeps the partial buffer and
more output groups. [Diagnosis](../experiments/own-xpu-runtime/stage2/packet54-compute/DIAGNOSIS.md).

The manifest seals five eligible candidates: route-rank4,
route-exp32-rank4, rows4-shared, rows8-shared and mix-vector4. Both norm proposals and
FFN combine-vector4 are closed before sealing. Eligible
outputs retain their original
arithmetic order, packet17 deterministic math and BF16 boundaries. M2 has
two serial rows; recurrence reloads the first row's rounded state.

The new packet independently needs 25 microseconds in both timing owners.
Its summary separately adds the exact bank and tests the 40-microsecond
integration trigger. Neither sum is a model throughput claim. Production
controls match packet49c SPEED6; the source checker verifies inherited
bodies and pins the bank receipt. [Preregistration](../experiments/own-xpu-runtime/stage2/packet54-compute/PREREGISTRATION.md).

Three subagents handled recurrence, routing, and HC/FFN kernels and source
analysis. Cross-review checked reduction trees, guards, M2 state carry,
event/capture counts, threshold accounting and integration sites. Review
caught an unsafe teardown path: an undrained owner now remains for the
coordinator rather than exiting. CPU compilation also caught an include
mirror resolution error, a wrong enum namespace and a test array initializer;
these are preparation failures, not device incidents.

The first GNU small test found a NaN-payload difference in combine. A scalar
fallback passed that helper comparison but failed actual compiled production:
BF16 `0x7fc0` versus `0x7fc1`. The arm is closed and its source/failure retained;
FFN remains control-only. No payload repair or tolerance is accepted.

The compiler-pair aggregate difference was localized byte by byte: finite
bytes agree, while norm controls choose different NaN payloads between GNU
and Intel. Exact candidate/control checks remain required within each
compiler. The finite cross-compiler digest and exceptional digests are recorded
separately; actual production norm parity then failed too, so both norm arms are closed.
The retained mix-only arm passes its finite and exceptional production check.

All preparation stays at nice 19 on cores 4–15,20–31, one compile at a time.
No GPU discovery/program, model oracle, service, protected chain or host
setting is used or changed. Build storage stays below 500 MB; only new
regenerable objects are removed after gates. Device work remains with the
coordinator after the packet49c chain releases ownership.

[Exact windows](../experiments/own-xpu-runtime/stage2/packet54-compute/WINDOW.md)
use script files, a past UTC review boundary, PF_EXITING-tolerant memory
sampling, fresh E/T owners, cooperative stops and hash-bound source/binaries.
[Integration map](../experiments/own-xpu-runtime/stage2/packet54-compute/INTEGRATION.md)
identifies each packet54 call site and the three banked packet53b calls.
No integration or public record change is part of this preparation.

The final active GNU/Intel pair passes 3329 assertions each with matching
finite and exceptional byte digests. One full M1 fixture passes all nine
production comparisons plus the separate exceptional mix case. All 17 wrapper
and decision tests pass. GNU, Intel and device compilation pass; no device code was run. Cleanup
leaves a 59.1 MB build, below the 500 MB cap. E1/E2 and T1/T2 remain the
coordinator's work. The final seal binds these sources, binaries and receipts.
[Preparation closeout](../experiments/own-xpu-runtime/stage2/packet54-compute/CPU-PREPARATION-CLOSEOUT.md).
