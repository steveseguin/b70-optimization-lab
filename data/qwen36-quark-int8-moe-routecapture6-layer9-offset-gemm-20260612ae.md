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
- Fused-prologue offset-GEMM max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `286.583 us`.
- Mean scratch `xpu_fused_moe`: `256.611 us`.
- Mean preallocated staged: `218.158 us`.
- Mean fused-prologue staged: `285.787 us`.
- Mean fused-prologue offset-GEMM staged: `213.233 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 299.241 | 268.166 | 233.128 | 296.320 | 219.587 | 101.854 | 106.359 | 179.284 |
| 1 | 4 | 8 | 287.583 | 259.924 | 217.648 | 289.305 | 214.446 | 97.684 | 97.200 | 169.660 |
| 1 | 8 | 8 | 265.073 | 239.691 | 201.923 | 265.394 | 199.359 | 90.556 | 91.211 | 158.928 |
| 1 | 12 | 8 | 265.124 | 239.576 | 202.621 | 265.223 | 198.267 | 90.700 | 94.255 | 159.583 |
| 1 | 16 | 8 | 310.922 | 272.116 | 230.497 | 299.650 | 228.335 | 102.083 | 102.561 | 178.513 |
| 1 | 20 | 8 | 291.479 | 262.532 | 223.484 | 293.103 | 218.688 | 100.164 | 97.890 | 172.987 |
| 1 | 24 | 8 | 283.046 | 253.372 | 215.358 | 279.992 | 208.487 | 95.389 | 95.522 | 168.007 |
| 1 | 28 | 8 | 265.354 | 240.108 | 202.881 | 264.437 | 197.737 | 90.451 | 90.752 | 159.423 |
| 1 | 32 | 8 | 264.779 | 239.808 | 203.141 | 265.852 | 198.505 | 90.421 | 91.563 | 160.609 |
| 1 | 36 | 8 | 264.493 | 238.507 | 201.691 | 263.730 | 198.858 | 91.246 | 91.579 | 159.758 |
| 1 | 40 | 8 | 270.353 | 247.378 | 209.877 | 274.111 | 204.162 | 93.194 | 93.156 | 163.077 |
| 1 | 44 | 8 | 284.967 | 256.695 | 217.249 | 285.795 | 213.060 | 95.995 | 95.836 | 168.913 |
| 1 | 48 | 8 | 307.925 | 271.896 | 230.199 | 301.343 | 226.987 | 102.927 | 102.086 | 180.544 |
| 1 | 52 | 8 | 264.113 | 239.299 | 201.269 | 265.035 | 197.664 | 90.769 | 90.752 | 158.545 |
| 1 | 56 | 8 | 290.195 | 261.693 | 220.284 | 295.053 | 218.663 | 98.134 | 98.493 | 172.106 |
| 1 | 60 | 8 | 370.677 | 315.009 | 279.280 | 368.243 | 268.916 | 123.635 | 123.651 | 209.673 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
