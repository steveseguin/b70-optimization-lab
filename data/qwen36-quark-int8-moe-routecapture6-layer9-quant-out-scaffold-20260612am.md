# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `16`.
- Quant out-variant available: `True`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.
- Fused-prologue staged max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `299.072 us`.
- Mean scratch `xpu_fused_moe`: `248.626 us`.
- Mean preallocated staged: `207.237 us`.
- Mean fused-prologue staged: `282.710 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 294.585 | 236.846 | 205.833 | 277.222 | n/a | n/a | 100.547 | 102.369 | 177.003 |
| 1 | 4 | 8 | 297.107 | 240.810 | 205.242 | 281.091 | n/a | n/a | 101.111 | 100.625 | 180.459 |
| 1 | 8 | 8 | 312.088 | 257.662 | 216.284 | 296.227 | n/a | n/a | 106.324 | 106.139 | 189.836 |
| 1 | 12 | 8 | 289.091 | 233.194 | 197.505 | 276.522 | n/a | n/a | 99.202 | 99.239 | 177.216 |
| 1 | 16 | 8 | 312.820 | 265.086 | 216.003 | 292.198 | n/a | n/a | 104.747 | 105.624 | 190.483 |
| 1 | 20 | 8 | 317.219 | 261.732 | 218.338 | 298.951 | n/a | n/a | 103.763 | 104.761 | 184.019 |
| 1 | 24 | 8 | 315.096 | 255.967 | 211.987 | 295.168 | n/a | n/a | 105.277 | 103.223 | 183.083 |
| 1 | 28 | 8 | 355.455 | 293.013 | 243.521 | 335.530 | n/a | n/a | 115.809 | 114.102 | 204.497 |
| 1 | 32 | 8 | 266.833 | 227.554 | 189.067 | 254.228 | n/a | n/a | 89.575 | 89.844 | 157.555 |
| 1 | 36 | 8 | 280.126 | 238.966 | 196.303 | 265.935 | n/a | n/a | 93.893 | 93.883 | 164.656 |
| 1 | 40 | 8 | 280.205 | 237.127 | 196.491 | 267.783 | n/a | n/a | 94.198 | 93.799 | 165.237 |
| 1 | 44 | 8 | 287.030 | 242.713 | 201.524 | 271.047 | n/a | n/a | 95.028 | 95.557 | 168.451 |
| 1 | 48 | 8 | 316.569 | 258.674 | 215.953 | 295.814 | n/a | n/a | 101.830 | 106.924 | 184.898 |
| 1 | 52 | 8 | 291.535 | 248.187 | 203.209 | 277.430 | n/a | n/a | 97.127 | 96.665 | 169.215 |
| 1 | 56 | 8 | 284.591 | 240.235 | 198.935 | 268.795 | n/a | n/a | 93.517 | 93.524 | 166.483 |
| 1 | 60 | 8 | 284.802 | 240.257 | 199.597 | 269.422 | n/a | n/a | 94.073 | 94.411 | 166.981 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
