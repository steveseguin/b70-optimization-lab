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

## Device result (card 0, 10:50-10:56 UTC, boot 2cba7160)

Windows `p54-a-{e1,e2,t1,t2}`; summary `packet54-compute/evidence/p54-a-summary.json` (ignored tree). There were no new fault lines (still the 2 reviewed lines from 01:09). The first launch refused before any device work because I passed a fault-review time 2 s in the future; the driver now computes it as now minus 60 s.

E1/E2 are byte-identical. Savings per ordinary M=1 layer (µs, T1/T2):

| Class | Selected | Saved | Notes |
|---|---|---:|---|
| route | route-exp32-rank4 | 5.52 / 5.52 | control 24.4 → 19.1; route-rank4 is equal |
| gdn.recurrence | rows4-shared | 1.04 / 1.04 | rows8-shared 0.4 |
| hc.inject_mix_norm | control | 0 | mix-vector4 was −33.8 (closed) |
| ffn.combine | control | 0 | closed at the CPU NaN-parity gate |

- Packet 54 total: **6.56 µs**, against its own 25 µs bar, so `compute_proceeds=false`.
- Banked p53b 23.44 + p54 6.56 = **30.0 µs**, against the 40 µs packet 49d trigger, so `packet49d_trigger=false`.

**Coordinator amendment (2026-10-17 10:58 UTC):** packet 49d proceeds anyway, with every exact winner: p53b expsgate v8-split, expsdown v16, small FFN v4; p54 route-exp32-rank4 and recurrence rows4-shared.

- **Why:** the 40 µs trigger was a resource gate for the roughly 2-hour device chain, not a quality or measurement gate.
- **What changed:** the cards are otherwise idle, and the 49d build was already underway.
- **Projection:** about 30 µs per layer is roughly 0.7 ms per half, about +3-4% (planning arithmetic, not a measurement).
- **Unchanged:** the 49d WS128 must still be exact against the packet 49 oracle and beat 45.695513 tok/s before any submission.
- **Trend:** exact-order kernel rounds now return 5-25 µs per layer. Larger levers need structural work (see packet 55, the one-card feasibility study).
