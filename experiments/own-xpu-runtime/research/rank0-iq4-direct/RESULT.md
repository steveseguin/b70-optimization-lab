# Direct-global IQ4_NL expert-down selection (2026-10-27)

A lab-only `OWNRT_IQ4_DIRECT=1` hook selected the already-compiled `p33.down.bank` implementation instead of the production R5 expert-down path. No new arithmetic or kernel body was introduced.

The full rank-0 run on card 27 matched B24 across **1,029 target buffers and 71 draft allocations**, with identical prefill/decode draft tokens and no other differing fields.

Device profiling showed no material gain:

| Arm | IQ4_NL down per half | Total device span per half |
|---|---:|---:|
| B24 R5 | **597.92 µs** | **10,129.2 µs** |
| `p33.down.bank` | 596.67 µs | 10,143.9 µs |

The 1.25 µs site difference is neutral and the total span is slightly worse. The hook was not integrated. Candidate binary: `21f87c58357f9cf7f4dbf2ff6024368d419f8070fece1432e3f3c1784a831f51`.
