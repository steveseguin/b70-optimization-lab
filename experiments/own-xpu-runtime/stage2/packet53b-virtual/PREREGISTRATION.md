# Packet53b preregistration

Question: can more independent logical chains and output rows recover at
least 35 µs per ordinary M=1 layer without changing a single output bit?
Packet53's common V4 choices saved 22.083/22.291 µs; persistent arms failed
and are excluded. No source from an external runtime is used.

| Class | Fixed candidates | Production control |
| --- | --- | --- |
| expsgate | paired V4 global; split-stream V8/V16 global | packet48b paired IQ2_S K2560, ten routes × 640 rows |
| expsdown | V4, V8, V16 | packet48b IQ4_NL K640, ten routes × 2560 rows |
| hc.low_gate | one V2/V4/V8 across a.low/a.gate/f.low/f.gate | packet51 accepted low Split4 and gate Split1, as in packet49c |
| small.ffn.q6 | V2, V4 | p30.small.rows4 four-member tuple used by packet49c |

The initially requested paired V16 carries 32 FP32 sum chains per physical lane. Register/spill
inspection is a CPU qualification gate before sealing. A spilling V16 must
be removed and replaced by a separately documented spill-free arm before
any device window; no timing-guided change to the arm list is permitted.

CPU register screening rejected paired V8/V16: both spilled at 128 GRFs.
A bounded-chain/scalar-decode alternative still spilled. The 256-GRF property
was refused by the installed offline compiler's SPIR-V reader, so it is not
registered. The admitted replacements use separate gate/up subgroups, each
with V8 or V16 chains and 128 GRFs; both reported zero spills in screening.
Final inspection repeats after matching the packet49c compact row pitch.
V4 retains the original paired scheduling and is remeasured, with its spill
status explicitly reported. No device timing guided these choices.

E1/E2 compare complete production outputs, statuses and sticky error to the
unchanged scalar production arithmetic and actual device control. Both fresh
processes must match. M2 is two independent serial rows, with distinct inputs
and routes. T1/T2 require both exact receipts, same boot/card/seal/environment
and reviewed past UTC fault boundary. They alternate candidate/control order,
10 excluded warmups plus 200 measured pairs for M1 and M2.

For each class maximize min(T1 saving,T2 saving), retaining control with zero
saving. Ties use lexical variant order. The **same** class choices must total
≥35 µs in each owner. HC is the sum of all four sites, not an average; small
FFN is one complete tuple. Savings use paired median completed compute-event
time. M2 does not affect selection and cannot rescue an M1 failure.

A pass goes directly to packet49d = packet49c plus selected winners in the
next brief. No oracle regeneration is needed for this exact-order mechanism.
This packet never launches a model or changes a protected engine.

Preparation is nice19, cores4–15,20–31, Python-B, one compiler at a time.
One GNU/Intel proof pair and one complete-shape host run, plus one small
sanitizer run and mocked window tests. Build cap 500 MB; preserve at least
18 GB root free at admission. No GPU, sudo, unit or host-setting changes.
