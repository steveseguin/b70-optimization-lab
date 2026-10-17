# Packet54 preregistration

CPU-only preparation; the coordinator alone runs card 0 PCI 0000:23:00.0.
The packet49c KD→WS128 chain and oracle remain protected. No GPU discovery,
service manipulation, host setting changes or model reads during preparation.

The manifest names five eligible candidates before sealing. The two norm
proposals and FFN vectorization are closed by actual-production NaN-payload
failures. Their source and failed receipts remain; mix is now tested alone.

| Class | Candidates |
| --- | --- |
| route | route-rank4; route-exp32-rank4 |
| gdn.recurrence | rows4-shared; rows8-shared |
| hc.inject_mix_norm | mix-vector4; production norms and injects |
| ffn.combine | control only; vectorization closed by production-byte failure |

Control is always packet49c's exact selected implementation. HC sums both
sides within each iteration; inject remains included and unchanged. This
isolated-class fixture preserves each member's production geometry and data
ABI, without claiming to model the intervening attention/FFN workload.
The synthetic fixture is operator evidence only, never a model benchmark.

E1/E2 use two finite full-shape fixtures at M1 and both serial M2 rows.
Every class output, recurrence state, route scratch and both norm partial
buffers are compared against an independent CPU control and the same-device
production implementation. Error, active and position are captured. Small
CPU fixtures additionally cover special values, inactive/sticky controls,
invalid positions, route ties and both recurrence head maps. M2 recurrence
row1 reads row0's actual BF16 state. There is no cross-row sum or FP32 carry.
Each E owner additionally compares one exceptional mix fixture against actual
compiled production, with all output/control bytes. Cross-compiler finite output
digests must match; exceptional NaN payloads must match the production path
within that compiler/backend, not a different compiler's payload choice.
No new model oracle job is needed or started: arithmetic identity is unchanged.

T1/T2 require both passing, identical E companions and fresh process owners.
Each timing arm restores inputs outside timing, alternates AB/BA by iteration,
runs ten warmups and 200 measured pairs. All class events are summed per row;
M2 sums both serial rows. Every timed pair also compares complete captured
outputs/state outside timing. No timing value comes from CPU or profiling.

For each class choose the variant maximizing its minimum paired-median M1
saving across T1 and T2; `control` with zero saving is allowed. Use those same
choices for both owners. Sum the per-class paired medians:

1. Packet54 independently proceeds when **both own totals ≥25 µs**.
2. Separately add p53b's **23.4385/23.4375 µs**, rounding only for display.
   **Both combined totals ≥40 µs** trigger preparation of packet49d, even if
   packet54's independent 25 µs bar is missed. This is a bank decision, not
   a claim that cross-packet savings have already been measured together.

M2 and every losing arm remain reported; neither rescues an M1 failure.
Integration must remeasure the combined implementation. No CPU gate, operator
speed sum or existing model record substitutes for packet49d qualification.

No retry loops. A fault or uncertain teardown retains evidence and stops
new launches; the coordinator owns recovery. A past UTC review boundary is
mandatory and cannot be a future scheduled window end.
