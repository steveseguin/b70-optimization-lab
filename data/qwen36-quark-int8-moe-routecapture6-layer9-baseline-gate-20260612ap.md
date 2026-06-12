# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `16`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.

## Timing

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 271.884 | 244.825 | 212.893 | 94.382 | 94.054 | 165.176 |
| 1 | 4 | 8 | 298.990 | 263.990 | 225.124 | 100.592 | 101.071 | 178.121 |
| 1 | 8 | 8 | 272.196 | 242.537 | 207.501 | 95.002 | 94.545 | 167.225 |
| 1 | 12 | 8 | 278.398 | 249.342 | 211.219 | 93.709 | 94.898 | 167.194 |
| 1 | 16 | 8 | 270.360 | 243.495 | 206.154 | 94.196 | 93.730 | 165.696 |
| 1 | 20 | 8 | 268.235 | 243.429 | 204.934 | 92.437 | 93.385 | 163.729 |
| 1 | 24 | 8 | 282.916 | 254.847 | 212.619 | 95.001 | 99.954 | 165.369 |
| 1 | 28 | 8 | 296.417 | 264.730 | 222.224 | 99.362 | 98.835 | 172.971 |
| 1 | 32 | 8 | 282.830 | 245.047 | 213.027 | 93.685 | 93.822 | 165.407 |
| 1 | 36 | 8 | 284.884 | 245.022 | 210.375 | 94.845 | 94.302 | 166.357 |
| 1 | 40 | 8 | 282.913 | 243.332 | 210.905 | 95.131 | 94.588 | 165.880 |
| 1 | 44 | 8 | 282.894 | 242.895 | 210.513 | 94.188 | 97.819 | 166.131 |
| 1 | 48 | 8 | 282.674 | 244.166 | 210.576 | 94.819 | 96.992 | 165.455 |
| 1 | 52 | 8 | 307.596 | 271.012 | 227.243 | 101.544 | 99.660 | 176.613 |
| 1 | 56 | 8 | 282.818 | 245.393 | 210.863 | 94.279 | 93.740 | 166.357 |
| 1 | 60 | 8 | 283.568 | 244.315 | 208.506 | 94.082 | 93.720 | 166.225 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
