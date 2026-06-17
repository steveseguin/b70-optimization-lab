# Qwen3.6 MoE Prologue Route Replay

- Result rows: `8`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28`.

## Timing

| rows | route start | active experts | current zero+remap us | fused prologue us | delta us | expand diff | count diff |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 108.033 | 103.839 | -4.194 | 0.000 | 0 |
| 1 | 4 | 8 | 107.825 | 102.885 | -4.940 | 0.000 | 0 |
| 1 | 8 | 8 | 105.469 | 104.889 | -0.580 | 0.000 | 0 |
| 1 | 12 | 8 | 107.520 | 103.017 | -4.503 | 0.000 | 0 |
| 1 | 16 | 8 | 106.678 | 106.231 | -0.447 | 0.000 | 0 |
| 1 | 20 | 8 | 105.713 | 103.462 | -2.252 | 0.000 | 0 |
| 1 | 24 | 8 | 108.064 | 103.347 | -4.716 | 0.000 | 0 |
| 1 | 28 | 8 | 106.150 | 102.749 | -3.401 | 0.000 | 0 |

## Decision

- Exact route expansion/count parity: `True`.
- Mean current zero+remap: `106.931 us`.
- Mean fused_moe_prologue: `103.802 us`.
- Existing fused_moe_prologue is a candidate for the next one-dispatch MoE layerlet screen.
