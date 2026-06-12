# Qwen3.6 W8A8 Grouped-GEMM M-Scaling Screen

Dry run: `True`
Inputs: `data/qwen36-quark-int8-tp4-hotrep-route-plan-l9-route6-20260612af.json, data/qwen36-quark-int8-tp4-hotrep-route-plan-l20-route5-20260612af.json`

## Aggregate

| stage | target rows | cases | us mean | TOPS mean | active BW TB/s | full-table BW TB/s | active experts mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemm1` | 32 | 10 | nan | nan | nan | nan | 23.1 |
| `gemm1` | 64 | 10 | nan | nan | nan | nan | 29.6 |
| `gemm1` | 128 | 10 | nan | nan | nan | nan | 43.4 |
| `gemm1` | 256 | 10 | nan | nan | nan | nan | 43.4 |
| `gemm1` | 512 | 10 | nan | nan | nan | nan | 43.4 |
| `gemm1` | 1024 | 10 | nan | nan | nan | nan | 43.4 |
| `gemm2` | 32 | 10 | nan | nan | nan | nan | 23.1 |
| `gemm2` | 64 | 10 | nan | nan | nan | nan | 29.6 |
| `gemm2` | 128 | 10 | nan | nan | nan | nan | 43.4 |
| `gemm2` | 256 | 10 | nan | nan | nan | nan | 43.4 |
| `gemm2` | 512 | 10 | nan | nan | nan | nan | 43.4 |
| `gemm2` | 1024 | 10 | nan | nan | nan | nan | 43.4 |

## Interpretation

- This artifact validates shape construction only. Run without `--dry-run` in a clean XPU window for timings.
