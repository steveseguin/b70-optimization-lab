# Qwen3.6 W8A8 Grouped-GEMM M-Scaling Screen

Dry run: `False`
Inputs: `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json, data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`

## Aggregate

| stage | target rows | cases | us mean | TOPS mean | active BW TB/s | full-table BW TB/s | active experts mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemm1` | 8 | 10 | 100.506 | 0.086 | 0.043 | 1.380 | 8.0 |
| `gemm1` | 16 | 10 | 93.443 | 0.180 | 0.083 | 1.442 | 14.7 |
| `gemm1` | 24 | 10 | 92.881 | 0.271 | 0.113 | 1.449 | 19.9 |
| `gemm1` | 32 | 10 | 92.897 | 0.361 | 0.132 | 1.449 | 23.1 |
| `gemm1` | 64 | 10 | 93.287 | 0.720 | 0.169 | 1.444 | 29.6 |
| `gemm1` | 128 | 10 | 93.285 | 1.439 | 0.248 | 1.446 | 43.4 |
| `gemm2` | 8 | 10 | 93.032 | 0.045 | 0.024 | 0.745 | 8.0 |
| `gemm2` | 16 | 10 | 93.586 | 0.090 | 0.043 | 0.740 | 14.7 |
| `gemm2` | 24 | 10 | 93.702 | 0.134 | 0.059 | 0.740 | 19.9 |
| `gemm2` | 32 | 10 | 93.099 | 0.180 | 0.069 | 0.745 | 23.1 |
| `gemm2` | 64 | 10 | 93.438 | 0.359 | 0.089 | 0.744 | 29.6 |
| `gemm2` | 128 | 10 | 93.972 | 0.715 | 0.131 | 0.743 | 43.4 |

## Interpretation

- If effective TOPS rises strongly with target rows, the current decode path is small-M/launch underutilized and persistent row aggregation is a strong candidate.
- If effective TOPS stays flat, the bottleneck is likely the kernel path/layout itself or a lower-level hardware/runtime limit.
