# Packet68c CPU preparation closeout

Question: can two rows share the tuned production weight/dequantization work
at ≤1.3× the M1 dense-class cost? Packet68b's slow generic implementation does
not answer that question.

Identity: copied packet68b; packet64 M1 arithmetic `iq3-p49-split32-v1` and
packet49 oracle; production-derived paired packet33/49c dense kernels and
packet65 wide64 experts. [Source pins](production-sources.json).

Outcome: the top four priorities plus QSA qgate, logits and shared expert down
are built. GNU and Intel pass 1,428 byte checks with the same bytes; the device
binary compiles, analyzer refusal tests pass and the 24/24 lane-B plan is
sealed. No GPU or CPU model run occurred. No H2/H1 or speed verdict exists.

Mechanism: preserve compile-time tiling, vector loads, gate/up split streams,
logical lane chains, reduction trees and BF16 boundaries; feed two independent
accumulator sets from each decoded weight. Stable expert union keeps output
slots in each row's original order. Consecutive engine inputs add differing
routes without a fourth full state clone.

Uncertainty: device register allocation, occupancy, differing-route overhead,
state identity and all thirteen exact streams still require the coordinator's
window. Router and HC classes stay explicitly serial in this first probe.
Consecutive snapshots do not qualify a causal M2 engine. Projection retains
the older 68b calibration and charges measured packet68 restore cost.

Retained evidence: [fixture](fixture/receipt.json),
[build](build-device-receipt.json), [plan](evidence/probe-plan.json),
[analyzer checks](evidence/analysis-tests.log), all source deltas and parent
manifest. Revisit after the coordinator returns per-class/half timings, or in
a separate sealed variant for the remaining serial classes. Preserve this seal
while its device window may be queued or running.
