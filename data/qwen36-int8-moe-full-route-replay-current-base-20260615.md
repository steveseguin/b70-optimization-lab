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
- Fused-prologue offset-GEMM max abs diff: `0.000`.
- Fused-prologue active-offset-GEMM max abs diff: `0.000`.

## Timing

- Mean `xpu_fused_moe`: `303.658 us`.
- Mean scratch `xpu_fused_moe`: `261.651 us`.
- Mean preallocated staged: `203.450 us`.
- Mean fused-prologue staged: `273.665 us`.
- Mean fused-prologue offset-GEMM staged: `198.924 us`.
- Mean fused-prologue active-offset-GEMM staged: `201.795 us`.

| rows | route start | active experts | xpu fused us | xpu scratch us | prealloc staged us | fused prologue staged us | fused prologue offset us | active offset us | gemm1 us | gemm2 us | act+quant2 us |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 316.259 | 279.110 | 222.485 | 296.754 | 210.033 | 215.524 | 100.412 | 102.991 | 181.431 |
| 1 | 4 | 8 | 302.149 | 257.852 | 201.804 | 269.199 | 198.887 | 201.149 | 95.547 | 96.036 | 167.336 |
| 1 | 8 | 8 | 321.625 | 275.114 | 214.560 | 287.355 | 211.585 | 214.139 | 100.157 | 100.168 | 175.978 |
| 1 | 12 | 8 | 303.714 | 256.246 | 199.930 | 272.483 | 197.415 | 199.446 | 94.962 | 94.245 | 166.839 |
| 1 | 16 | 8 | 322.059 | 273.398 | 211.936 | 283.954 | 208.289 | 211.276 | 100.001 | 106.735 | 183.248 |
| 1 | 20 | 8 | 303.711 | 254.714 | 196.719 | 267.571 | 195.655 | 197.644 | 95.794 | 95.495 | 167.970 |
| 1 | 24 | 8 | 280.158 | 253.726 | 192.777 | 257.286 | 185.484 | 188.230 | 91.016 | 90.184 | 159.242 |
| 1 | 28 | 8 | 279.591 | 243.051 | 187.390 | 254.717 | 184.046 | 186.953 | 90.787 | 90.763 | 158.725 |

## Prologue-Inclusive Gate

- Gate status: `exact_nonreference_candidates_exist_but_gate_not_met`.
- Rows ready for endpoint gate: `0` / `8`.
- Best exact non-reference full-layerlet candidate: `fused_prologue_offset_gemm` at `184.046 us` (`1.519x` vs current `xpu_fused_moe`).
- Endpoint promotion allowed by this artifact: `False`.
- Endpoint promotion still requires graph-path tensor capture, accepted-lane quality gates, and a manifest update.

| rows | route start | best exact nonref | best nonref us | speedup vs xpu | target met | status |
|---:|---:|---|---:|---:|---:|---|
| 1 | 0 | fused_prologue_offset_gemm | 210.033 | 1.506 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 4 | fused_prologue_offset_gemm | 198.887 | 1.519 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 8 | fused_prologue_offset_gemm | 211.585 | 1.520 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 12 | fused_prologue_offset_gemm | 197.415 | 1.538 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 16 | fused_prologue_offset_gemm | 208.289 | 1.546 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 20 | fused_prologue_offset_gemm | 195.655 | 1.552 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 24 | fused_prologue_offset_gemm | 185.484 | 1.510 | False | best_exact_nonreference_misses_target_layerlet_us |
| 1 | 28 | fused_prologue_offset_gemm | 184.046 | 1.519 | False | best_exact_nonreference_misses_target_layerlet_us |

## Decision

- This is a baseline route replay with the current non-fused activation and quantization path.
- The fused-prologue staged path is exact against `xpu_fused_moe` for this route replay.
- The fused-prologue staged path is slower than the simpler preallocated staged path in this full-MoE screen. Do not wire it into the endpoint unless the downstream GEMM ABI can consume prologue offsets directly or the prologue is fused with more downstream work.
- Compare `xpu fused us` with the current budget target of roughly `160 us/layer` for a plausible `200 tok/s` non-speculative lane.
