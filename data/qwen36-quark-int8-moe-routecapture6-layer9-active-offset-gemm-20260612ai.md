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
- Fused-prologue active-offset-GEMM max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `304.448 us`.
- Mean scratch `xpu_fused_moe`: `267.360 us`.
- Mean preallocated staged: `226.882 us`.
- Mean fused-prologue staged: `302.865 us`.
- Mean fused-prologue offset-GEMM staged: `225.162 us`.
- Mean fused-prologue active-offset-GEMM staged: `225.911 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 280.347 | 249.347 | 211.333 | 278.684 | 214.571 | 207.182 | 93.047 | 93.076 | 165.026 |
| 1 | 4 | 8 | 293.128 | 257.486 | 219.122 | 289.441 | 213.573 | 218.995 | 98.139 | 96.861 | 170.377 |
| 1 | 8 | 8 | 279.832 | 250.960 | 211.731 | 277.335 | 206.120 | 211.099 | 96.274 | 97.410 | 171.043 |
| 1 | 12 | 8 | 265.063 | 240.241 | 204.700 | 266.726 | 197.561 | 196.727 | 91.071 | 90.891 | 159.306 |
| 1 | 16 | 8 | 359.172 | 309.141 | 261.606 | 369.622 | 282.559 | 273.502 | 122.476 | 118.201 | 216.160 |
| 1 | 20 | 8 | 378.047 | 320.844 | 270.793 | 394.003 | 287.630 | 280.498 | 125.609 | 125.080 | 221.647 |
| 1 | 24 | 8 | 365.347 | 308.653 | 268.175 | 354.332 | 261.123 | 263.722 | 125.830 | 121.911 | 216.165 |
| 1 | 28 | 8 | 310.864 | 276.773 | 231.262 | 308.913 | 228.672 | 229.868 | 104.689 | 104.278 | 182.745 |
| 1 | 32 | 8 | 337.434 | 289.491 | 244.366 | 327.721 | 240.054 | 246.719 | 114.186 | 112.170 | 195.122 |
| 1 | 36 | 8 | 282.684 | 248.897 | 215.391 | 280.726 | 208.821 | 209.816 | 95.583 | 99.724 | 167.839 |
| 1 | 40 | 8 | 290.462 | 255.986 | 217.957 | 282.613 | 210.870 | 215.056 | 97.519 | 97.078 | 168.733 |
| 1 | 44 | 8 | 286.368 | 256.646 | 215.623 | 284.719 | 209.830 | 214.082 | 98.212 | 97.988 | 170.974 |
| 1 | 48 | 8 | 274.264 | 245.420 | 207.408 | 275.003 | 204.222 | 208.295 | 94.892 | 94.014 | 165.288 |
| 1 | 52 | 8 | 268.896 | 238.332 | 202.285 | 264.448 | 202.163 | 202.078 | 91.684 | 91.729 | 160.186 |
| 1 | 56 | 8 | 313.347 | 273.660 | 230.212 | 297.200 | 220.021 | 223.498 | 104.719 | 104.891 | 181.511 |
| 1 | 60 | 8 | 285.915 | 255.879 | 218.142 | 294.350 | 214.804 | 213.446 | 97.347 | 97.156 | 170.356 |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
