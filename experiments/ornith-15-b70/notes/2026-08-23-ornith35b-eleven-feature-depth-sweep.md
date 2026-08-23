# Ornith 1.5 35B-A3B: eleven-feature context-depth sweep

Date: 2026-08-23 EDT

The accepted eleven-feature package was measured directly at seven explicit
context depths on one Intel Arc Pro B70. Every point is the mean of five
`llama-bench` repetitions with graph capture off, flash attention on, F16 KV,
`pp2048`, and `tg128`. No point is interpolated or extrapolated.

| Existing context | Prefill pp2048 (tok/s) | Decode tg128 (tok/s) |
| ---: | ---: | ---: |
| 0 | 1397.348168 ± 37.934260 | 138.977520 ± 0.488091 |
| 2,048 | 1326.651018 ± 7.407945 | 133.765934 ± 0.349082 |
| 4,096 | 1312.167851 ± 5.005357 | 130.620489 ± 0.102782 |
| 8,192 | 1284.796086 ± 5.813444 | 124.209778 ± 0.089241 |
| 16,384 | 1220.200931 ± 6.057906 | 113.310860 ± 0.099154 |
| 24,576 | 1196.724116 ± 5.810693 | 104.315441 ± 0.053836 |
| 32,768 | 1101.625369 ± 3.946584 | 96.995532 ± 0.060964 |

The raw JSON is
`../../../repro/ornith-15-35b-a3b-q4km-b70/ornith-15-35b-a3b-q4km-eleven-feature.sweep.json`;
its SHA-256 is
`6716b6e28842e3a81ee2befd9db5d0ef6f821dae7bbafd78babc0b48518a09c1`.
The adjacent metadata binds the model, benchmark executable, SYCL library,
runtime revision, complete patch, environment doors, and activation count.
