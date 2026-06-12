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
- Fused-prologue staged max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `288.237 us`.
- Mean scratch `xpu_fused_moe`: `258.465 us`.
- Mean preallocated staged: `216.361 us`.
- Mean fused-prologue staged: `284.705 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 290.730 | 260.414 | 218.031 | 294.694 | 99.939 | 95.848 | 172.976 |
| 1 | 4 | 8 | 306.207 | 277.080 | 228.684 | 304.510 | 101.989 | 100.691 | 177.592 |
| 1 | 8 | 8 | 289.316 | 261.506 | 217.142 | 287.628 | 96.827 | 102.159 | 172.021 |
| 1 | 12 | 8 | 290.094 | 258.587 | 214.996 | 283.090 | 96.112 | 98.854 | 172.773 |
| 1 | 16 | 8 | 284.527 | 257.897 | 218.183 | 282.634 | 94.248 | 95.387 | 167.865 |
| 1 | 20 | 8 | 280.632 | 252.307 | 211.559 | 277.829 | 92.654 | 93.226 | 165.533 |
| 1 | 24 | 8 | 302.557 | 268.570 | 227.649 | 299.939 | 99.388 | 100.105 | 179.743 |
| 1 | 28 | 8 | 305.996 | 269.358 | 221.959 | 294.641 | 101.483 | 99.975 | 176.803 |
| 1 | 32 | 8 | 280.100 | 253.165 | 211.422 | 277.375 | 94.231 | 93.295 | 166.364 |
| 1 | 36 | 8 | 289.186 | 256.322 | 217.310 | 284.352 | 95.515 | 95.510 | 168.799 |
| 1 | 40 | 8 | 264.557 | 240.734 | 202.225 | 262.903 | 89.523 | 89.558 | 159.602 |
| 1 | 44 | 8 | 295.188 | 261.250 | 219.452 | 290.167 | 98.003 | 97.237 | 172.195 |
| 1 | 48 | 8 | 279.514 | 251.325 | 209.771 | 274.986 | 93.520 | 94.106 | 166.589 |
| 1 | 52 | 8 | 293.067 | 263.304 | 219.809 | 287.848 | 97.817 | 98.550 | 174.143 |
| 1 | 56 | 8 | 292.365 | 262.895 | 221.731 | 288.413 | 98.514 | 95.623 | 169.853 |
| 1 | 60 | 8 | 267.751 | 240.725 | 201.852 | 264.267 | 89.650 | 89.360 | 158.170 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
