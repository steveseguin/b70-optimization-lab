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

- Mean `xpu_fused_moe`: `409.229 us`.
- Mean scratch `xpu_fused_moe`: `445.174 us`.
- Mean preallocated staged: `226.876 us`.
- Mean fused-prologue staged: `297.177 us`.
- Mean fused-prologue offset-GEMM staged: `225.970 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 397.836 | 443.859 | 222.472 | 287.365 | 219.333 | n/a | 101.478 | 92.830 | 162.791 |
| 1 | 1 | 8 | 398.050 | 435.588 | 220.854 | 287.669 | 219.164 | n/a | 91.863 | 92.232 | 160.844 |
| 1 | 2 | 8 | 402.217 | 433.883 | 223.662 | 289.975 | 218.421 | n/a | 93.478 | 93.210 | 162.885 |
| 1 | 3 | 8 | 397.740 | 434.099 | 224.476 | 287.947 | 223.928 | n/a | 92.396 | 96.481 | 171.608 |
| 1 | 4 | 8 | 399.885 | 436.028 | 222.269 | 299.624 | 221.413 | n/a | 93.369 | 95.456 | 164.858 |
| 1 | 5 | 8 | 399.779 | 437.271 | 223.002 | 290.394 | 220.828 | n/a | 92.986 | 93.816 | 162.952 |
| 1 | 6 | 8 | 424.336 | 457.356 | 232.539 | 310.315 | 235.430 | n/a | 98.652 | 98.423 | 170.773 |
| 1 | 7 | 8 | 426.566 | 458.052 | 232.679 | 305.900 | 233.860 | n/a | 97.672 | 98.272 | 171.860 |
| 1 | 8 | 8 | 418.181 | 456.557 | 231.382 | 306.301 | 231.150 | n/a | 98.392 | 97.310 | 170.076 |
| 1 | 9 | 8 | 416.465 | 450.908 | 230.724 | 301.322 | 230.909 | n/a | 96.590 | 96.257 | 171.306 |
| 1 | 10 | 8 | 421.554 | 454.587 | 230.940 | 302.947 | 230.225 | n/a | 96.704 | 97.367 | 169.952 |
| 1 | 11 | 8 | 408.140 | 443.906 | 227.508 | 296.369 | 226.983 | n/a | 95.709 | 100.399 | 166.262 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
