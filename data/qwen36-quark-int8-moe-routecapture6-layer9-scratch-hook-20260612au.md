# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `16`.
- Quant out-variant available: `False`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.
- Fused-prologue staged max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `309.978 us`.
- Mean scratch `xpu_fused_moe`: `346.038 us`.
- Mean preallocated staged: `250.135 us`.
- Mean fused-prologue staged: `333.010 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 334.124 | 376.497 | 277.437 | 366.467 | n/a | n/a | 110.635 | 110.842 | 191.786 |
| 1 | 4 | 8 | 362.257 | 402.552 | 290.296 | 383.512 | n/a | n/a | 119.502 | 119.105 | 208.978 |
| 1 | 8 | 8 | 373.103 | 404.011 | 292.276 | 401.010 | n/a | n/a | 122.526 | 119.946 | 212.510 |
| 1 | 12 | 8 | 380.013 | 417.540 | 302.048 | 404.067 | n/a | n/a | 124.955 | 121.589 | 215.134 |
| 1 | 16 | 8 | 322.439 | 360.034 | 260.474 | 344.521 | n/a | n/a | 108.813 | 106.491 | 188.261 |
| 1 | 20 | 8 | 264.027 | 298.910 | 215.738 | 286.014 | n/a | n/a | 89.916 | 89.815 | 158.339 |
| 1 | 24 | 8 | 289.245 | 324.037 | 235.308 | 311.403 | n/a | n/a | 98.573 | 96.683 | 170.282 |
| 1 | 28 | 8 | 289.401 | 325.488 | 234.515 | 310.110 | n/a | n/a | 97.852 | 97.078 | 170.762 |
| 1 | 32 | 8 | 292.490 | 323.886 | 235.072 | 313.394 | n/a | n/a | 98.616 | 96.717 | 173.315 |
| 1 | 36 | 8 | 276.897 | 313.197 | 224.372 | 297.679 | n/a | n/a | 94.331 | 93.288 | 163.229 |
| 1 | 40 | 8 | 283.570 | 320.750 | 229.144 | 305.508 | n/a | n/a | 95.425 | 95.514 | 168.457 |
| 1 | 44 | 8 | 298.600 | 333.258 | 239.593 | 318.670 | n/a | n/a | 100.873 | 100.880 | 175.118 |
| 1 | 48 | 8 | 331.603 | 372.075 | 270.349 | 361.574 | n/a | n/a | 111.399 | 110.112 | 193.798 |
| 1 | 52 | 8 | 285.780 | 318.792 | 229.294 | 305.578 | n/a | n/a | 96.388 | 96.169 | 169.198 |
| 1 | 56 | 8 | 282.028 | 314.046 | 226.810 | 302.025 | n/a | n/a | 94.917 | 94.569 | 166.542 |
| 1 | 60 | 8 | 294.068 | 331.531 | 239.440 | 316.622 | n/a | n/a | 99.739 | 98.683 | 174.199 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
