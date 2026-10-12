# Packet 42 on card 2 (2026-10-12 15:20–15:27 UTC): launch floor measured; first faster route kernel

K0, T1 (launch-floor benchmark) and K2 (candidates) passed after the compile-smoke fix
([evidence](../evidence/20261012-k0-empty-bindings/README.md)); every admitted
candidate is byte-equal to its incumbent on the card; clean kernel log.

## Launch floor ([table](launch-table.md), [medians](launch-summary-medians.json))

A kernel that does one trivial element-wise BF16 operation on N elements, 200
repetitions per shape, GPU event time per launch:

| N | cheapest shape | GPU median | costliest shape tried | GPU median |
| ---: | --- | ---: | --- | ---: |
| 1–32 | plain range, one pointer to a parameter block | 0.52 µs | by-value arguments, four launches | 4.7–5.0 µs |
| 640 | work-group 32, parameter pointer | 0.63 µs | work-group with an unused local accessor | 7.0 µs |
| 2,560–10,240 | work-group 32, parameter pointer | 0.73 µs | work-group with barrier and unused local memory | 9.6–11.7 µs |
| 25,600 | work-group 256, parameter pointer | 0.73 µs | the same | 13.4 µs |

Readings: (1) the card's floor for one more launch is **0.5–1.5 µs** of GPU time, not
the 3–11 µs our small kernels take, so what those kernels pay for is their shape and
body; (2) a barrier, unused local memory, or a 32-lane work-group in which one lane
works each cost several µs per launch; (3) a by-value argument block costs 0.2–0.9 µs
more per launch than one pointer to a parameter block for trivial kernels; (4) host
wall per submit-and-wait is about 9–11 µs, which is why GPU event time, not wall, is
the metric here.

## Candidates ([table](table.md), [selection](dispatch-measured.json))

| Class | Candidate | Per token | Note |
| --- | --- | ---: | --- |
| **route** | `p42.route.production_rank32` (four launches, parallel stable rank with 16 comparisons per lane) | **−1.22 ms** | first route form faster than the incumbent five-launch one (68 µs per group) |
| routed expert gate/up | `p42.gate.packed` | −0.24 ms | under the 10% threshold, not selected by the rule; real but small |
| re-shaped tiny kernels | gdn.gated, qsa.prepare, qsa.select, qsa.pool, HC activations, combines | about −0.3 ms together | each 0.02–0.05 ms |
| gdn.recurrence | `p42.gdn.token1` | −0.05 ms | small |
| routed expert down | `p42.down.select_vector`, `bank_scalar` | +0.8, +1.0 ms | slower although they issue fewer memory messages: message count does not rank these kernels |
| attention projection | `p42.dense.fourparts` | — | **failed its exactness case on the card** after passing the CPU gates; not usable until explained |
| norms, moe combine, expert activation, gdn.conv re-shaped | | +0.1 to +0.2 ms | slower: their bodies, not their launch shape, set their cost |

Usable total from this packet: about 1.7 ms per token (route 1.2, gate 0.24, tiny 0.3).
