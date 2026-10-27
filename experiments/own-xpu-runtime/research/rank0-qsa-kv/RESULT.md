# QSA K/V sibling fusion (2026-10-27)

Adding `qsa.k + qsa.v` to the existing same-type sibling-fusion table registered two rank-0 pairs (layers 3 and 15), increasing `decode-fusion.json` pairs from 92 to 94. No arithmetic changed.

The full rank-0 comparison against the current B25 reference passed all **1,029 target buffers and 71 draft allocations**, with identical prefill/decode draft tokens and no other differing fields.

| Arm | Q6_K K site | Q6_K V site | Total device span per half |
|---|---:|---:|---:|
| B25 | 38.44 µs | 27.50 µs | 10,138.0 µs |
| K/V fused | 50.21 µs | 9.27 µs | 10,128.4 µs |

The fused sites save about 6.5 µs, but the whole-span difference is only 9.6 µs (0.09%) and is not a material service win. The change was not integrated. Candidate binary: `44fb6659b22373b13722d40fa4291deaf84ec5dd6f74cef7a1587f4b318da697`.
