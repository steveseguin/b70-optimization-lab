# Ornith 1.5 35B-A3B: twelve-feature context-depth sweep

Date: 2026-08-23 EDT

The complete twelve-feature package and accepted Level Zero copy-offload
setting were measured directly at seven explicit context depths on one Intel
Arc Pro B70. Every point is the mean of five `llama-bench` repetitions with
graph capture off, flash attention on, F16 KV, `pp2048`, and `tg128`. No point
is interpolated or extrapolated.

| Existing context | Prefill pp2048 (tok/s) | Decode tg128 (tok/s) |
| ---: | ---: | ---: |
| 0 | 1422.407346 ± 47.893822 | 141.917514 ± 0.432292 |
| 2,048 | 1343.876428 ± 9.407195 | 136.848608 ± 0.126625 |
| 4,096 | 1338.212192 ± 5.211605 | 133.329784 ± 0.055994 |
| 8,192 | 1301.167019 ± 7.720143 | 126.829116 ± 0.069566 |
| 16,384 | 1238.569995 ± 4.898119 | 116.267169 ± 0.021548 |
| 24,576 | 1212.927246 ± 6.482580 | 106.967195 ± 0.279634 |
| 32,768 | 1115.599876 ± 3.375252 | 99.614237 ± 0.096554 |

The raw JSON is
`../../../repro/ornith-15-35b-a3b-q4km-b70/ornith-15-35b-a3b-q4km-twelve-feature.sweep.json`;
its SHA-256 is
`98f9539f5611146634e5fb11a8d29ddf1477af4c0a9e9857be52e3edffb671b5`.
The adjacent metadata binds the model, benchmark executable, SYCL library,
runtime revision, complete patch, all runtime doors, and 179,480 observed
twelfth-feature hits. The generated SVG is stored beside the sweep.
