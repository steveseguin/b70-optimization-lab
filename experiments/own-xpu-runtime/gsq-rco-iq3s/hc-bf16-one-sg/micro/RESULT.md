# HC one-subgroup geometry: exact, insufficient benefit

The fixed native comparison passed all56 full-output pairs and112 kernel launches.
Both candidate outputs match the unchanged control and saved original-baseline
outputs byte for byte. The real backend contact/nonce ACK, safe zero-live teardown,
physical drain and unchanged fault/vision/queue checks all pass independently.
Four warmup pairs per shape are excluded; every24 measured pair is retained,
12 AB and12 BA, with balanced case position.

| Fixed layer0 case | Control mean (µs) | Candidate mean (µs) | B/A | AB B/A | BA B/A |
| --- | ---: | ---: | ---: | ---: | ---: |
| HC low, N320/K10240 | 51.796917 | 51.158708 | 0.987679 | 0.987747 | 0.987611 |
| HC inject, N4/K10240 | 48.949542 | 49.045125 | 1.001953 | 1.004605 | 0.999292 |

These are repeated isolated kernel event durations on fixed diagnostic fixtures,
not full-model throughput. Low saves about0.64µs; inject shows no useful gain.
The geometry lever is closed without full-engine integration: this narrow gain
is too small to justify an engine campaign. No end-to-end extrapolation is promoted.
Current qualified a0f9 engine remains unchanged. No weights, precision, KV cache,
arithmetic order or target verification changed.

[Independent actual review](operating/evidence/device-a/review.json):
`9498ae30ff5a13be52feb8b7663aa1d8843a483d05fc59606d3ae09be6e8a7ed`.
Binary: `46ab2be7298bf1a3b306c851201f88ee5e3ebfc6746a8c1afd3e8d9ee331abca`.
Plan: `ef4d2e8d82eea2c0402772e3510c767a3e1507b5b21cd22b2d6490a5f2fa57b6`.
Coordinator duration2.392seconds includes setup and closure. No automatic retry,
cooperative signal, new fault or model request occurred.
