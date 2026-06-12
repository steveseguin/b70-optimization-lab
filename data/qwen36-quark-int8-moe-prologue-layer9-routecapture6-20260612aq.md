# Qwen3.6 MoE Prologue Route Replay

- Result rows: `16`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.

## Timing

| rows | route start | active experts | current zero+remap us | fused prologue us | delta us | expand diff | count diff |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 101.492 | 97.450 | -4.042 | 0.000 | 0 |
| 1 | 4 | 8 | 103.036 | 96.921 | -6.115 | 0.000 | 0 |
| 1 | 8 | 8 | 100.294 | 98.956 | -1.338 | 0.000 | 0 |
| 1 | 12 | 8 | 102.534 | 96.391 | -6.143 | 0.000 | 0 |
| 1 | 16 | 8 | 104.962 | 98.176 | -6.786 | 0.000 | 0 |
| 1 | 20 | 8 | 105.030 | 101.533 | -3.496 | 0.000 | 0 |
| 1 | 24 | 8 | 132.149 | 126.705 | -5.444 | 0.000 | 0 |
| 1 | 28 | 8 | 107.713 | 101.767 | -5.945 | 0.000 | 0 |
| 1 | 32 | 8 | 105.303 | 102.012 | -3.292 | 0.000 | 0 |
| 1 | 36 | 8 | 107.316 | 103.497 | -3.819 | 0.000 | 0 |
| 1 | 40 | 8 | 105.721 | 102.565 | -3.156 | 0.000 | 0 |
| 1 | 44 | 8 | 113.057 | 109.600 | -3.456 | 0.000 | 0 |
| 1 | 48 | 8 | 124.965 | 124.857 | -0.107 | 0.000 | 0 |
| 1 | 52 | 8 | 137.835 | 132.002 | -5.833 | 0.000 | 0 |
| 1 | 56 | 8 | 122.708 | 115.958 | -6.750 | 0.000 | 0 |
| 1 | 60 | 8 | 103.617 | 97.807 | -5.810 | 0.000 | 0 |

## Decision

- Exact route expansion/count parity: `True`.
- Mean current zero+remap: `111.108 us`.
- Mean fused_moe_prologue: `106.637 us`.
- Existing fused_moe_prologue is a candidate for the next one-dispatch MoE layerlet screen.
