# Qwen3.6 W8A8 Grouped-GEMM M-Scaling Screen

Dry run: `False`
Inputs: `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json, data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`

## Aggregate

| stage | target rows | cases | us mean | TOPS mean | active BW TB/s | full-table BW TB/s | active experts mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemm1` | 32 | 10 | 111.628 | 0.309 | 0.112 | 1.239 | 23.1 |
| `gemm1` | 64 | 10 | 112.938 | 0.605 | 0.142 | 1.213 | 29.6 |
| `gemm1` | 128 | 10 | 107.196 | 1.281 | 0.223 | 1.286 | 43.4 |
| `gemm1` | 256 | 10 | 102.215 | 2.667 | 0.234 | 1.343 | 43.4 |
| `gemm1` | 512 | 10 | 93.805 | 5.731 | 0.258 | 1.450 | 43.4 |
| `gemm1` | 1024 | 10 | 106.699 | 10.272 | 0.245 | 1.312 | 43.4 |
| `gemm2` | 32 | 10 | 110.462 | 0.154 | 0.059 | 0.638 | 23.1 |
| `gemm2` | 64 | 10 | 108.577 | 0.313 | 0.078 | 0.648 | 29.6 |
| `gemm2` | 128 | 10 | 101.541 | 0.671 | 0.124 | 0.697 | 43.4 |
| `gemm2` | 256 | 10 | 101.566 | 1.340 | 0.129 | 0.702 | 43.4 |
| `gemm2` | 512 | 10 | 101.423 | 2.682 | 0.139 | 0.713 | 43.4 |
| `gemm2` | 1024 | 10 | 105.324 | 5.193 | 0.156 | 0.711 | 43.4 |

## Interpretation

- If effective TOPS rises strongly with target rows, the current decode path is small-M/launch underutilized and persistent row aggregation is a strong candidate.
- If effective TOPS stays flat, the bottleneck is likely the kernel path/layout itself or a lower-level hardware/runtime limit.
