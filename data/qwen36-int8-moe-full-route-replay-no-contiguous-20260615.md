# Qwen3.6 INT8 MoE Route Replay

- Fused SiLU+quant enabled: `False`.
- TP size: `4`.
- Result rows: `8`.
- Quant out-variant available: `True`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28`.
- Prologue-inclusive target: `160.000 us/layerlet`.
- Exactness threshold: `0.000000`.

## Exactness

- Manual staged max abs diff versus `xpu_fused_moe`: `0.000`.
- Scratch `xpu_fused_moe` max abs diff: `0.000`.
- Preallocated staged max abs diff: `0.000`.
- Fused-prologue staged max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `297.473 us`.
- Mean scratch `xpu_fused_moe`: `249.339 us`.
- Mean preallocated staged: `195.981 us`.
- Mean fused-prologue staged: `263.348 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 299.237 | 244.943 | 193.120 | 260.517 | n/a | n/a | 93.449 | 93.293 | 171.977 |
| 1 | 4 | 8 | 290.620 | 242.221 | 191.794 | 255.551 | n/a | n/a | 90.467 | 90.007 | 158.582 |
| 1 | 8 | 8 | 301.057 | 256.633 | 201.968 | 269.178 | n/a | n/a | 95.134 | 95.688 | 165.937 |
| 1 | 12 | 8 | 306.566 | 258.055 | 202.927 | 273.991 | n/a | n/a | 94.362 | 98.023 | 166.907 |
| 1 | 16 | 8 | 297.266 | 249.085 | 195.777 | 262.119 | n/a | n/a | 92.225 | 93.132 | 163.114 |
| 1 | 20 | 8 | 289.229 | 241.114 | 189.621 | 255.013 | n/a | n/a | 90.545 | 91.042 | 158.673 |
| 1 | 24 | 8 | 294.700 | 246.054 | 193.492 | 260.294 | n/a | n/a | 92.971 | 93.103 | 161.785 |
| 1 | 28 | 8 | 301.109 | 256.607 | 199.147 | 270.124 | n/a | n/a | 95.971 | 95.430 | 168.163 |

## Prologue-Inclusive Gate

- Gate status: `exact_nonreference_candidates_exist_but_gate_not_met`.
- Rows ready for endpoint gate: `0` / `8`.
- Best exact non-reference full-layerlet candidate: `preallocated_staged` at `189.621 us` (`1.525x` vs current `xpu_fused_moe`).
- Endpoint promotion allowed by this artifact: `False`.
- Endpoint promotion still requires graph-path tensor capture, accepted-lane quality gates, and a manifest update.

| rows | route start | best exact nonref | best nonref us | speedup vs xpu | target met | status |
|---:|---:|---|---:|---:|---:|---|
| 1 | 0 | preallocated_staged | 193.120 | 1.549 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 4 | preallocated_staged | 191.794 | 1.515 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 8 | preallocated_staged | 201.968 | 1.491 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 12 | preallocated_staged | 202.927 | 1.511 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 16 | preallocated_staged | 195.777 | 1.518 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 20 | preallocated_staged | 189.621 | 1.525 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 24 | preallocated_staged | 193.492 | 1.523 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 28 | preallocated_staged | 199.147 | 1.512 | False | best_exact_nonreference_misses_target_layerlet_us |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
