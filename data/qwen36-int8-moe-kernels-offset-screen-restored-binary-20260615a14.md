# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `16`.
- Quant out-variant available: `True`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.
- Prologue-inclusive target: `160.000 us/layerlet`.
- Exactness threshold: `0.000000`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.
- Fused-prologue staged max abs diff: `0.000`.
- Fused-prologue offset-GEMM max abs diff: `0.000`.
- Fused-prologue active-offset-GEMM max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `308.477 us`.
- Mean scratch `xpu_fused_moe`: `259.163 us`.
- Mean preallocated staged: `202.470 us`.
- Mean fused-prologue staged: `275.297 us`.
- Mean fused-prologue offset-GEMM staged: `202.215 us`.
- Mean fused-prologue active-offset-GEMM staged: `203.472 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 308.646 | 257.001 | 207.563 | 275.978 | 203.717 | 205.929 | 98.264 | 97.145 | 169.520 |
| 1 | 4 | 8 | 300.680 | 255.537 | 201.880 | 271.820 | 197.832 | 198.945 | 95.179 | 95.309 | 165.939 |
| 1 | 8 | 8 | 319.403 | 268.644 | 207.910 | 285.600 | 210.470 | 210.385 | 101.230 | 100.816 | 177.492 |
| 1 | 12 | 8 | 301.016 | 242.365 | 195.537 | 268.488 | 193.721 | 198.155 | 92.843 | 93.238 | 164.852 |
| 1 | 16 | 8 | 323.643 | 264.404 | 211.032 | 288.763 | 209.094 | 212.352 | 100.764 | 101.091 | 175.323 |
| 1 | 20 | 8 | 300.752 | 267.672 | 195.012 | 268.577 | 193.005 | 196.948 | 93.109 | 93.156 | 165.284 |
| 1 | 24 | 8 | 303.403 | 244.851 | 190.987 | 266.857 | 197.026 | 199.841 | 94.181 | 93.976 | 163.985 |
| 1 | 28 | 8 | 317.216 | 265.165 | 206.787 | 286.794 | 206.232 | 210.673 | 98.836 | 98.058 | 174.737 |
| 1 | 32 | 8 | 299.671 | 251.110 | 198.507 | 270.452 | 194.811 | 196.621 | 93.482 | 93.579 | 166.312 |
| 1 | 36 | 8 | 314.654 | 263.947 | 204.708 | 278.736 | 201.824 | 203.580 | 97.824 | 95.964 | 171.468 |
| 1 | 40 | 8 | 299.567 | 253.646 | 198.503 | 269.606 | 221.263 | 199.214 | 94.347 | 93.777 | 166.709 |
| 1 | 44 | 8 | 296.944 | 256.039 | 198.186 | 268.405 | 196.706 | 198.236 | 94.500 | 94.539 | 167.913 |
| 1 | 48 | 8 | 300.009 | 254.947 | 199.709 | 267.885 | 195.265 | 199.176 | 93.983 | 94.735 | 165.357 |
| 1 | 52 | 8 | 301.976 | 254.476 | 200.431 | 270.218 | 195.652 | 199.072 | 93.987 | 94.033 | 166.268 |
| 1 | 56 | 8 | 339.468 | 283.428 | 218.017 | 291.867 | 214.420 | 220.307 | 103.596 | 102.525 | 181.161 |
| 1 | 60 | 8 | 308.578 | 263.370 | 204.747 | 274.707 | 204.405 | 206.112 | 96.855 | 97.115 | 170.787 |

## Prologue-Inclusive Gate

- Gate status: `exact_nonreference_candidates_exist_but_gate_not_met`.
- Rows ready for endpoint gate: `0` / `16`.
- Best exact non-reference full-layerlet candidate: `preallocated_staged` at `190.987 us` (`1.589x` vs current `xpu_fused_moe`).
- Endpoint promotion allowed by this artifact: `False`.
- Endpoint promotion still requires graph-path tensor capture, accepted-lane quality gates, and a manifest update.

| rows | route start | best exact nonref | best nonref us | speedup vs xpu | target met | status |
|---:|---:|---|---:|---:|---:|---|
| 1 | 0 | fused_prologue_offset_gemm | 203.717 | 1.515 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 4 | fused_prologue_offset_gemm | 197.832 | 1.520 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 8 | preallocated_staged | 207.910 | 1.536 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 12 | fused_prologue_offset_gemm | 193.721 | 1.554 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 16 | fused_prologue_offset_gemm | 209.094 | 1.548 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 20 | fused_prologue_offset_gemm | 193.005 | 1.558 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 24 | preallocated_staged | 190.987 | 1.589 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 28 | fused_prologue_offset_gemm | 206.232 | 1.538 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 32 | fused_prologue_offset_gemm | 194.811 | 1.538 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 36 | fused_prologue_offset_gemm | 201.824 | 1.559 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 40 | preallocated_staged | 198.503 | 1.509 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 44 | fused_prologue_offset_gemm | 196.706 | 1.510 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 48 | fused_prologue_offset_gemm | 195.265 | 1.536 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 52 | fused_prologue_offset_gemm | 195.652 | 1.543 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 56 | fused_prologue_offset_gemm | 214.420 | 1.583 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 60 | fused_prologue_offset_gemm | 204.405 | 1.510 | False | best_exact_nonreference_misses_target_layerlet_us |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
