# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `True`.
- TP size: `4`.
- Result rows: `16`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.750`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.750`.

## Timing

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 260.054 | 234.432 | 215.413 | 94.278 | 94.286 | 167.983 |
| 1 | 4 | 8 | 256.565 | 233.305 | 209.447 | 94.286 | 94.283 | 166.230 |
| 1 | 8 | 8 | 258.457 | 230.128 | 208.191 | 93.467 | 94.103 | 165.105 |
| 1 | 12 | 8 | 257.026 | 230.688 | 206.943 | 94.955 | 94.188 | 167.163 |
| 1 | 16 | 8 | 280.644 | 250.075 | 227.659 | 101.774 | 100.662 | 182.728 |
| 1 | 20 | 8 | 269.171 | 244.546 | 216.887 | 98.325 | 97.152 | 174.640 |
| 1 | 24 | 8 | 279.450 | 251.859 | 225.926 | 101.929 | 101.012 | 179.657 |
| 1 | 28 | 8 | 301.813 | 261.889 | 237.359 | 106.170 | 103.957 | 184.522 |
| 1 | 32 | 8 | 275.343 | 249.229 | 226.283 | 99.646 | 101.388 | 177.481 |
| 1 | 36 | 8 | 276.600 | 248.820 | 222.217 | 100.357 | 99.563 | 175.911 |
| 1 | 40 | 8 | 270.485 | 247.326 | 225.261 | 97.710 | 97.651 | 171.888 |
| 1 | 44 | 8 | 276.902 | 252.899 | 230.057 | 102.717 | 100.490 | 178.530 |
| 1 | 48 | 8 | 295.903 | 274.941 | 240.878 | 107.976 | 108.862 | 187.855 |
| 1 | 52 | 8 | 276.791 | 252.285 | 220.643 | 99.665 | 99.440 | 175.516 |
| 1 | 56 | 8 | 287.995 | 262.824 | 233.837 | 103.941 | 102.818 | 181.296 |
| 1 | 60 | 8 | 242.590 | 222.269 | 198.671 | 88.773 | 89.608 | 156.903 |

## Decision

- The fused SiLU+quant candidate is not exact against the manual staged path for this route replay. Do not promote it as a no-quality-loss path.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
