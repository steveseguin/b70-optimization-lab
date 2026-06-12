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

- Mean `xpu_fused_moe`: `304.732 us`.
- Mean scratch `xpu_fused_moe`: `328.756 us`.
- Mean preallocated staged: `233.977 us`.
- Mean fused-prologue staged: `310.735 us`.
- Mean fused-prologue offset-GEMM staged: `240.725 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 311.532 | 332.297 | 234.364 | 306.211 | 240.413 | n/a | 96.737 | 99.424 | 178.187 |
| 1 | 1 | 8 | 301.895 | 325.156 | 228.921 | 310.232 | 241.124 | n/a | 101.140 | 98.748 | 173.836 |
| 1 | 2 | 8 | 300.768 | 328.813 | 238.645 | 315.761 | 240.639 | n/a | 96.373 | 97.552 | 174.720 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
