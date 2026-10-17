# Packet54 compute preparation — closeout

<!-- campaign-closeout -->

## Question and identity

October 17 CPU-only preparation for packet49c SPEED6's ordinary GDN M=1/M=2
classes, using packet17 deterministic math and unchanged BF16 state. No
weights or GPU were read. The coordinator owns physical card 0 PCI 0000:23:00.0;
packet49c KD→WS128 and the model oracle remain protected. See [control
identity](control-identity.json), [manifest](manifest.json) and [diagnosis](DIAGNOSIS.md).

## Outcome

Five candidates are eligible for device checking: two route schedules,
rows4/rows8 recurrence, and vectorized HC mixing. Norm/inject remain production;
FFN is control-only. No new speed is measured. The own-packet 25 µs bar and
banked-plus-new 40 µs trigger both remain pending.

GNU and Intel each pass3329 small identity assertions in one bounded run,
with the same finite output SHA256
`e76fb970dc83dd7d35fe9e55f3e73d48408d342f6d484bc72680095f2b6de1c7`.
The separately retained 24 exceptional HC bytes also agree across both compilers
and exactly against each compiler's control. These checks include route ties,
recurrence state/controls and M2, and HC guards/special values. The count is
assertions, not model tokens or rows.
One complete GNU M1 fixture passes all 9 production-shape class/arm comparisons
plus 1 exceptional actual-production HC mix comparison. This uses the same
submission path as the eventual E windows, not an algebra-only oracle.
The 17 mocked coordinator/parser tests and GNU/Intel/device builds pass.
Device compilation did not execute or enumerate a GPU. The build peaked at
66,792,228 recorded bytes; cleanup removed 7,711,044 bytes of own regenerable
objects, leaving 59,081,184 bytes with binaries, mirrors and logs retained.
Device execution remains pending.

## What worked

Production ABI/source checks caught appended active/error bindings and prevent
using earlier unrelated controls. Full compiled-production comparisons caught
failures that helper-only tests missed. Exact byte gates narrowed the eligible
packet before any GPU slot. M2 retains each arm's own rounded recurrence state.
The source diagnosis supports head math sharing and route division reuse as
large opportunities, while avoiding another underoccupied norm fusion.

## What failed or remains uncertain

FFN combine and both norm proposals failed actual-production NaN-payload
parity and were closed, despite ordinary finite cases passing. Their compiled
failure receipts, source and reproducible fixtures are retained in
[rejected arms](REJECTED-ARMS.md); no tolerance or output repair was adopted.
The earlier mixed-arm compiler digest difference was localized to explicit
NaN fixtures using complete retained byte dumps. Closed helper tests are
archived, not part of the active eligibility gate.
Earlier include/enum/shape and binding errors were corrected during preparation.
No failure here was a GPU incident. Device arithmetic, generated code occupancy,
register spilling, timing and integrated model behavior remain unmeasured.

## Evidence and patches

- [CPU receipts](cpu-gates.json), [wrapper tests](python-gates.json), and
  [review](REVIEW.md).
- New independent kernels: [recurrence](recurrence.hpp), [route](route.hpp),
  [HC/FFN source including rejected arms](hc_ffn.hpp).
- [Compiler byte-difference proof](evidence-cpu/cross-compiler-byte-range-proof.json)
  and [lossless diagnostic retention](evidence-cpu/diagnostic-retention.json).
- [Build/restore commands](CPU-BUILD.md), [retention rules](RETENTION.md),
  [integration map](INTEGRATION.md), [coordinator windows](WINDOW.md).

## When to revisit

The coordinator runs E1/E2 and then T1/T2 after card ownership is released,
with a real past UTC fault-review boundary. Each E has 54 ordinary comparisons
plus 1 exceptional mix comparison; each T has 6300 records and 25200 compute
events. Require a common M1 selection in both owners. Packet54 independently
needs 25 µs; adding p53b's exact 23.4385/23.4375 µs must reach 40 µs in both owners
to trigger packet49d. Only that later integration can establish combined gain.
Reopen closed norm/FFN proposals only with an exact compiled-production
solution whose overhead can justify the remaining budget. Keep existing oracle
identity; no new oracle job is required for unchanged-order eligible candidates.
