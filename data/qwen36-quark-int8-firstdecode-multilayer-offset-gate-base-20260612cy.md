# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `12`.
- Quant out-variant available: `False`.
- Route source: `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`.
- Route records matched: `12`; top-k rows loaded: `12`.
- Route start indices: `0,1,2,3,4,5,6,7,8,9,10,11`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.
- Fused-prologue staged max abs diff: `0.000`.
- Fused-prologue offset-GEMM max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `347.086 us`.
- Mean scratch `xpu_fused_moe`: `382.570 us`.
- Mean preallocated staged: `269.608 us`.
- Mean fused-prologue staged: `356.576 us`.
- Mean fused-prologue offset-GEMM staged: `269.867 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 295.799 | 331.079 | 234.533 | 315.827 | 234.031 | n/a | 96.327 | 98.987 | 168.568 |
| 1 | 1 | 8 | 385.614 | 437.447 | 293.288 | 383.344 | 289.450 | n/a | 118.144 | 117.276 | 213.655 |
| 1 | 2 | 8 | 293.576 | 328.476 | 228.311 | 297.489 | 225.576 | n/a | 95.573 | 94.240 | 166.686 |
| 1 | 3 | 8 | 371.584 | 401.188 | 283.104 | 382.860 | 288.548 | n/a | 118.131 | 113.295 | 199.155 |
| 1 | 4 | 8 | 377.296 | 430.719 | 294.315 | 399.326 | 301.631 | n/a | 118.227 | 125.502 | 215.935 |
| 1 | 5 | 8 | 348.176 | 376.264 | 265.647 | 352.888 | 266.846 | n/a | 109.395 | 109.208 | 188.219 |
| 1 | 6 | 8 | 336.440 | 378.435 | 265.096 | 354.614 | 265.086 | n/a | 111.436 | 109.457 | 190.427 |
| 1 | 7 | 8 | 314.080 | 338.247 | 246.254 | 319.566 | 241.251 | n/a | 99.008 | 99.310 | 178.079 |
| 1 | 8 | 8 | 402.399 | 435.412 | 321.615 | 412.984 | 324.688 | n/a | 122.920 | 121.038 | 219.716 |
| 1 | 9 | 8 | 339.968 | 369.512 | 262.647 | 345.756 | 268.991 | n/a | 107.520 | 109.447 | 188.292 |
| 1 | 10 | 8 | 363.371 | 393.338 | 277.711 | 370.705 | 276.042 | n/a | 113.207 | 111.558 | 194.719 |
| 1 | 11 | 8 | 336.723 | 370.721 | 262.774 | 343.556 | 256.261 | n/a | 111.441 | 113.870 | 200.468 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
