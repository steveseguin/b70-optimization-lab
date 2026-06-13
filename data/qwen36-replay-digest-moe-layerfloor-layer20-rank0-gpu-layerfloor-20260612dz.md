# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `16`.
- Quant out-variant available: `False`.
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

## Timing

- Mean `xpu_fused_moe`: `290.622 us`.
- Mean scratch `xpu_fused_moe`: `322.331 us`.
- Mean preallocated staged: `226.341 us`.
- Mean fused-prologue staged: `302.343 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 286.248 | 316.273 | 221.043 | 302.935 | n/a | n/a | 92.748 | 93.047 | 169.315 |
| 1 | 1 | 8 | 308.654 | 346.512 | 239.290 | 320.796 | n/a | n/a | 99.891 | 99.121 | 176.219 |
| 1 | 2 | 8 | 293.614 | 325.629 | 228.976 | 304.539 | n/a | n/a | 94.743 | 93.998 | 169.803 |
| 1 | 3 | 8 | 294.134 | 325.941 | 228.067 | 303.775 | n/a | n/a | 94.905 | 95.267 | 168.847 |
| 1 | 4 | 8 | 306.121 | 339.292 | 238.255 | 316.039 | n/a | n/a | 98.632 | 100.965 | 176.550 |
| 1 | 5 | 8 | 299.469 | 331.633 | 233.441 | 310.589 | n/a | n/a | 96.772 | 99.844 | 171.458 |
| 1 | 6 | 8 | 278.706 | 311.717 | 219.643 | 289.964 | n/a | n/a | 91.359 | 91.356 | 160.537 |
| 1 | 7 | 8 | 275.787 | 309.755 | 217.342 | 287.884 | n/a | n/a | 90.457 | 90.988 | 159.412 |
| 1 | 8 | 8 | 276.043 | 311.098 | 217.678 | 287.904 | n/a | n/a | 91.026 | 91.269 | 159.068 |
| 1 | 9 | 8 | 286.650 | 322.696 | 226.132 | 299.725 | n/a | n/a | 93.513 | 94.206 | 164.443 |
| 1 | 10 | 8 | 291.531 | 323.869 | 227.813 | 302.662 | n/a | n/a | 93.263 | 94.142 | 167.106 |
| 1 | 11 | 8 | 297.323 | 328.665 | 231.222 | 307.957 | n/a | n/a | 96.723 | 95.999 | 170.202 |
| 1 | 12 | 8 | 278.468 | 310.549 | 219.586 | 291.184 | n/a | n/a | 90.827 | 90.960 | 161.177 |
| 1 | 13 | 8 | 292.729 | 311.886 | 220.875 | 304.534 | n/a | n/a | 94.630 | 93.926 | 169.157 |
| 1 | 14 | 8 | 292.174 | 323.801 | 226.897 | 303.332 | n/a | n/a | 94.788 | 97.405 | 167.621 |
| 1 | 15 | 8 | 292.298 | 317.984 | 225.200 | 303.670 | n/a | n/a | 99.963 | 95.225 | 161.312 |

## Prologue-Inclusive Gate

- Gate status: `exact_nonreference_candidates_exist_but_gate_not_met`.
- Rows ready for endpoint gate: `0` / `16`.
- Best exact non-reference full-layerlet candidate: `preallocated_staged` at `217.342 us` (`1.269x` vs current `xpu_fused_moe`).
- Endpoint promotion allowed by this artifact: `False`.
- Endpoint promotion still requires graph-path tensor capture, accepted-lane quality gates, and a manifest update.

| rows | route start | best exact nonref | best nonref us | speedup vs xpu | target met | status |
|---:|---:|---|---:|---:|---:|---|
| 1 | 0 | preallocated_staged | 221.043 | 1.295 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 1 | preallocated_staged | 239.290 | 1.290 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 2 | preallocated_staged | 228.976 | 1.282 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 3 | preallocated_staged | 228.067 | 1.290 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 4 | preallocated_staged | 238.255 | 1.285 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 5 | preallocated_staged | 233.441 | 1.283 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 6 | preallocated_staged | 219.643 | 1.269 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 7 | preallocated_staged | 217.342 | 1.269 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 8 | preallocated_staged | 217.678 | 1.268 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 9 | preallocated_staged | 226.132 | 1.268 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 10 | preallocated_staged | 227.813 | 1.280 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 11 | preallocated_staged | 231.222 | 1.286 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 12 | preallocated_staged | 219.586 | 1.268 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 13 | preallocated_staged | 220.875 | 1.325 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 14 | preallocated_staged | 226.897 | 1.288 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 15 | preallocated_staged | 225.200 | 1.298 | False | best_exact_nonreference_misses_target_layerlet_us |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
