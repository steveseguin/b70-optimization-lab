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

## Timing

- Mean `xpu_fused_moe`: `302.545 us`.
- Mean scratch `xpu_fused_moe`: `259.336 us`.
- Mean preallocated staged: `203.157 us`.
- Mean fused-prologue staged: `273.989 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 321.291 | 268.618 | 214.122 | 282.526 | n/a | n/a | 97.975 | 97.342 | 170.444 |
| 1 | 4 | 8 | 287.806 | 246.752 | 193.709 | 261.605 | n/a | n/a | 91.815 | 91.669 | 161.573 |
| 1 | 8 | 8 | 288.813 | 249.813 | 194.376 | 262.759 | n/a | n/a | 92.487 | 92.347 | 162.784 |
| 1 | 12 | 8 | 281.965 | 243.825 | 190.786 | 257.504 | n/a | n/a | 89.996 | 89.906 | 157.974 |
| 1 | 16 | 8 | 290.651 | 249.959 | 196.265 | 264.196 | n/a | n/a | 92.295 | 92.595 | 162.252 |
| 1 | 20 | 8 | 284.159 | 243.563 | 192.019 | 258.010 | n/a | n/a | 90.898 | 90.204 | 158.987 |
| 1 | 24 | 8 | 284.794 | 250.224 | 194.743 | 261.357 | n/a | n/a | 91.569 | 91.400 | 160.626 |
| 1 | 28 | 8 | 287.468 | 249.368 | 196.095 | 263.921 | n/a | n/a | 91.806 | 92.557 | 162.091 |
| 1 | 32 | 8 | 309.481 | 269.147 | 210.664 | 282.240 | n/a | n/a | 98.667 | 99.672 | 175.367 |
| 1 | 36 | 8 | 332.653 | 280.810 | 220.813 | 303.285 | n/a | n/a | 108.527 | 103.698 | 182.140 |
| 1 | 40 | 8 | 339.492 | 282.483 | 221.257 | 299.834 | n/a | n/a | 103.695 | 104.137 | 183.170 |
| 1 | 44 | 8 | 317.552 | 274.723 | 215.025 | 289.257 | n/a | n/a | 99.594 | 101.717 | 176.003 |
| 1 | 48 | 8 | 325.865 | 283.360 | 215.545 | 293.712 | n/a | n/a | 103.560 | 101.421 | 178.996 |
| 1 | 52 | 8 | 312.879 | 262.529 | 205.861 | 279.933 | n/a | n/a | 97.987 | 99.722 | 173.774 |
| 1 | 56 | 8 | 293.096 | 249.666 | 198.044 | 265.789 | n/a | n/a | 93.591 | 93.546 | 166.199 |
| 1 | 60 | 8 | 282.757 | 244.533 | 191.192 | 257.889 | n/a | n/a | 90.407 | 91.094 | 157.818 |

## Prologue-Inclusive Gate

- Gate status: `exact_nonreference_candidates_exist_but_gate_not_met`.
- Rows ready for endpoint gate: `0` / `16`.
- Best exact non-reference full-layerlet candidate: `preallocated_staged` at `190.786 us` (`1.478x` vs current `xpu_fused_moe`).
- Endpoint promotion allowed by this artifact: `False`.
- Endpoint promotion still requires graph-path tensor capture, accepted-lane quality gates, and a manifest update.

| rows | route start | best exact nonref | best nonref us | speedup vs xpu | target met | status |
|---:|---:|---|---:|---:|---:|---|
| 1 | 0 | preallocated_staged | 214.122 | 1.501 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 4 | preallocated_staged | 193.709 | 1.486 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 8 | preallocated_staged | 194.376 | 1.486 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 12 | preallocated_staged | 190.786 | 1.478 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 16 | preallocated_staged | 196.265 | 1.481 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 20 | preallocated_staged | 192.019 | 1.480 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 24 | preallocated_staged | 194.743 | 1.462 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 28 | preallocated_staged | 196.095 | 1.466 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 32 | preallocated_staged | 210.664 | 1.469 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 36 | preallocated_staged | 220.813 | 1.506 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 40 | preallocated_staged | 221.257 | 1.534 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 44 | preallocated_staged | 215.025 | 1.477 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 48 | preallocated_staged | 215.545 | 1.512 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 52 | preallocated_staged | 205.861 | 1.520 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 56 | preallocated_staged | 198.044 | 1.480 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 60 | preallocated_staged | 191.192 | 1.479 | False | best_exact_nonreference_misses_target_layerlet_us |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
