# Ornith 1.5 35B-A3B: ten-feature context-depth sweep

Date: 2026-08-23 EDT

Status: **published as the current package curve**

The complete ten-feature stack, including in-place GDN state I/O, was measured
at seven explicit context depths. Every point used one B70, graph off, flash
attention on, F16 K/V cache, `pp2048`, `tg128`, and five repetitions.

| Existing depth | decode tg128 tok/s (±σ) | prefill pp2048 tok/s (±σ) |
| ---: | ---: | ---: |
| 0 | 135.347557 (±0.537328) | 1400.713008 (±37.897953) |
| 2,048 | 130.735400 (±0.308501) | 1324.708989 (±8.115282) |
| 4,096 | 127.705931 (±0.142006) | 1316.755210 (±4.471018) |
| 8,192 | 121.263474 (±0.080977) | 1283.591011 (±9.069970) |
| 16,384 | 110.938268 (±0.102753) | 1219.310576 (±6.951988) |
| 24,576 | 102.288946 (±0.119344) | 1196.442256 (±8.378890) |
| 32,768 | 95.021893 (±0.083691) | 1102.085345 (±3.214645) |

No point is interpolated or extrapolated. Raw engine rates are not the same
metric as the fresh HTTP serving mean. The sweep recorded 134,610 in-place
GDN state I/O hits. Raw JSON, binary/model identities, patch identity, exact
environment, and the rendered chart live in the package under
`repro/ornith-15-35b-a3b-q4km-b70/`.
