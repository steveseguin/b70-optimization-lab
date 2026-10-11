# Packet 25 G1 on card 0: large-GEMV candidates, exact, but little faster than the runtime's own kernels (2026-10-11 20:34–20:39 UTC)

Two fresh owners, clean kernel log. Exactness: every candidate is bit-identical to the
current kernel on the card for all fixtures; current equals the host for every finite
element and infinity; 104 elements differ from the host only in NaN encoding (a card
NaN where the host has a NaN), which the model path never produces as output.

Median GPU execution time per launch group (µs), owner 1; owner 2 agrees within 1%:

| Class | "current" in this harness | best candidate | the runtime's R5 kernel, measured in the model |
| --- | ---: | ---: | ---: |
| expert down (IQ4_NL) | 483.9 | private_decode 120.1 | 130 |
| expert gate/up (IQ2_S) | 448.7 | wg32 168.6 | 178 |
| gdn.qkv (Q6) | 219.8 | rows4 84.6 | 101 |
| gdn.z (Q6) | 123.5 | wide8 51.0 | 62 |
| qsa.qgate | 263.1 | rows4 104.8 | 118 |
| logits | 5,244.6 | rows4 2,268.5 | 2,137 |
| attention out (gdn / qsa) | 51.4 / 51.5 | none faster | — |

**Reading.** The harness's "current" kernel is about 2.5 times slower than the kernels
the runtime actually runs with the R5 dispatch (last column, from
`packet18-decode-v2/evidence/20261011-host-bottleneck-location-scan`), so the 2.3–4×
gains in the harness table are not gains for the runtime. Against the runtime's real
kernels the best candidates are 5–20% faster (about 2 ms per token in total), and
logits is slower. The expert kernels stay near 170 µs per launch group, 60–70 GB/s on
packed bytes, where six earlier kernel rounds also ended. The "staged" decode-then-GEMV
idea is twice as slow as the direct kernels.

A like-for-like comparison (the runtime's R5 kernel and these candidates in one timing
run at the same shapes) belongs to packet 26's per-class timing gate.
