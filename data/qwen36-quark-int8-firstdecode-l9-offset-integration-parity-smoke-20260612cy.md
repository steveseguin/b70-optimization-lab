# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `3`.
- Quant out-variant available: `False`.
- Route source: `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`.
- Route records matched: `3`; top-k rows loaded: `3`.
- Route start indices: `0,1,2`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.
- Fused-prologue staged max abs diff: `0.000`.
- Fused-prologue offset-GEMM max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `419.530 us`.
- Mean scratch `xpu_fused_moe`: `465.348 us`.
- Mean preallocated staged: `236.115 us`.
- Mean fused-prologue staged: `306.026 us`.
- Mean fused-prologue offset-GEMM staged: `237.657 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 422.760 | 450.337 | 235.577 | 309.452 | 233.567 | n/a | 97.725 | 95.923 | 172.259 |
| 1 | 1 | 8 | 423.367 | 507.069 | 232.371 | 301.929 | 244.036 | n/a | 98.765 | 95.715 | 174.616 |
| 1 | 2 | 8 | 412.464 | 438.637 | 240.396 | 306.696 | 235.369 | n/a | 95.056 | 99.857 | 165.603 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
