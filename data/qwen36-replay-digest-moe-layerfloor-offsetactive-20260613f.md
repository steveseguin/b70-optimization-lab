# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `16`.
- Quant out-variant available: `True`.
- Route source: `data/qwen36-replay-digest-hot-decode1-layer20-rank0-routes-20260612dv.jsonl`.
- Route records matched: `347`; top-k rows loaded: `347`.
- Route start indices: `0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15`.
- Prologue-inclusive target: `125.000 us/layerlet`.
- Exactness threshold: `0.000000`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.
- Fused-prologue staged max abs diff: `0.000`.
- Fused-prologue offset-GEMM max abs diff: `0.000`.
- Fused-prologue active-offset-GEMM max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `315.292 us`.
- Mean scratch `xpu_fused_moe`: `268.168 us`.
- Mean preallocated staged: `211.869 us`.
- Mean fused-prologue staged: `286.142 us`.
- Mean fused-prologue offset-GEMM staged: `209.052 us`.
- Mean fused-prologue active-offset-GEMM staged: `211.170 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 291.061 | 251.061 | 201.647 | 266.770 | 195.374 | 198.854 | 101.156 | 93.327 | 163.717 |
| 1 | 1 | 8 | 316.064 | 275.435 | 217.690 | 294.081 | 213.541 | 213.977 | 101.492 | 102.089 | 187.772 |
| 1 | 2 | 8 | 315.667 | 266.093 | 213.847 | 288.161 | 212.101 | 209.546 | 101.449 | 101.232 | 175.227 |
| 1 | 3 | 8 | 309.717 | 263.546 | 204.854 | 275.278 | 201.686 | 208.204 | 100.468 | 97.538 | 171.383 |
| 1 | 4 | 8 | 378.349 | 318.795 | 252.063 | 354.223 | 262.840 | 254.444 | 119.202 | 119.283 | 213.209 |
| 1 | 5 | 8 | 359.446 | 304.483 | 237.406 | 318.189 | 230.525 | 236.896 | 116.710 | 112.800 | 202.693 |
| 1 | 6 | 8 | 302.058 | 256.649 | 202.540 | 275.557 | 200.089 | 203.475 | 96.821 | 98.456 | 170.876 |
| 1 | 7 | 8 | 307.884 | 267.211 | 209.807 | 285.597 | 204.552 | 208.391 | 100.535 | 99.144 | 172.914 |
| 1 | 8 | 8 | 290.868 | 250.945 | 198.194 | 266.405 | 194.598 | 196.615 | 95.364 | 94.338 | 165.084 |
| 1 | 9 | 8 | 291.490 | 249.495 | 197.591 | 265.054 | 194.527 | 196.310 | 93.636 | 94.432 | 162.694 |
| 1 | 10 | 8 | 285.279 | 243.706 | 192.824 | 259.000 | 190.025 | 191.555 | 92.156 | 91.815 | 161.548 |
| 1 | 11 | 8 | 289.496 | 248.681 | 195.009 | 265.058 | 196.446 | 195.541 | 94.337 | 94.471 | 164.199 |
| 1 | 12 | 8 | 296.040 | 245.023 | 195.962 | 264.980 | 193.337 | 196.213 | 94.494 | 94.342 | 165.304 |
| 1 | 13 | 8 | 316.111 | 268.267 | 212.862 | 285.869 | 210.629 | 211.242 | 101.618 | 101.965 | 176.280 |
| 1 | 14 | 8 | 330.970 | 290.833 | 228.791 | 303.525 | 218.511 | 224.996 | 106.046 | 104.172 | 183.213 |
| 1 | 15 | 8 | 364.168 | 290.462 | 228.813 | 310.528 | 226.057 | 232.454 | 108.776 | 107.523 | 187.775 |

## Prologue-Inclusive Gate

- Gate status: `exact_nonreference_candidates_exist_but_gate_not_met`.
- Rows ready for endpoint gate: `0` / `16`.
- Best exact non-reference full-layerlet candidate: `fused_prologue_offset_gemm` at `190.025 us` (`1.501x` vs current `xpu_fused_moe`).
- Endpoint promotion allowed by this artifact: `False`.
- Endpoint promotion still requires graph-path tensor capture, accepted-lane quality gates, and a manifest update.

| rows | route start | best exact nonref | best nonref us | speedup vs xpu | target met | status |
|---:|---:|---|---:|---:|---:|---|
| 1 | 0 | fused_prologue_offset_gemm | 195.374 | 1.490 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 1 | fused_prologue_offset_gemm | 213.541 | 1.480 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 2 | fused_prologue_active_offset_gemm | 209.546 | 1.506 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 3 | fused_prologue_offset_gemm | 201.686 | 1.536 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 4 | preallocated_staged | 252.063 | 1.501 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 5 | fused_prologue_offset_gemm | 230.525 | 1.559 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 6 | fused_prologue_offset_gemm | 200.089 | 1.510 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 7 | fused_prologue_offset_gemm | 204.552 | 1.505 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 8 | fused_prologue_offset_gemm | 194.598 | 1.495 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 9 | fused_prologue_offset_gemm | 194.527 | 1.498 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 10 | fused_prologue_offset_gemm | 190.025 | 1.501 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 11 | preallocated_staged | 195.009 | 1.485 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 12 | fused_prologue_offset_gemm | 193.337 | 1.531 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 13 | fused_prologue_offset_gemm | 210.629 | 1.501 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 14 | fused_prologue_offset_gemm | 218.511 | 1.515 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 15 | fused_prologue_offset_gemm | 226.057 | 1.611 | False | best_exact_nonreference_misses_target_layerlet_us |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
