# Qwen3.6 MoE Prologue Route Replay

- Result rows: `16`.
- Route source: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`.
- Route records matched: `95`; top-k rows loaded: `95`.
- Route start indices: `0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60`.

## Timing

| rows | route start | active experts | current zero+remap us | fused prologue us | delta us | expand diff | count diff |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 100.584 | 97.601 | -2.983 | 0.000 | 0 |
| 1 | 4 | 8 | 101.613 | 95.501 | -6.112 | 0.000 | 0 |
| 1 | 8 | 8 | 99.544 | 96.535 | -3.009 | 0.000 | 0 |
| 1 | 12 | 8 | 106.265 | 99.597 | -6.668 | 0.000 | 0 |
| 1 | 16 | 8 | 105.082 | 100.363 | -4.718 | 0.000 | 0 |
| 1 | 20 | 8 | 105.768 | 102.109 | -3.659 | 0.000 | 0 |
| 1 | 24 | 8 | 104.335 | 100.894 | -3.441 | 0.000 | 0 |
| 1 | 28 | 8 | 103.184 | 99.667 | -3.517 | 0.000 | 0 |
| 1 | 32 | 8 | 103.846 | 100.282 | -3.564 | 0.000 | 0 |
| 1 | 36 | 8 | 103.201 | 100.812 | -2.389 | 0.000 | 0 |
| 1 | 40 | 8 | 103.359 | 100.686 | -2.673 | 0.000 | 0 |
| 1 | 44 | 8 | 102.000 | 98.020 | -3.980 | 0.000 | 0 |
| 1 | 48 | 8 | 101.149 | 97.628 | -3.520 | 0.000 | 0 |
| 1 | 52 | 8 | 101.483 | 98.788 | -2.695 | 0.000 | 0 |
| 1 | 56 | 8 | 100.454 | 97.677 | -2.777 | 0.000 | 0 |
| 1 | 60 | 8 | 100.381 | 97.687 | -2.694 | 0.000 | 0 |

## Decision

- Exact route expansion/count parity: `True`.
- Mean current zero+remap: `102.640 us`.
- Mean fused_moe_prologue: `98.990 us`.
- Existing fused_moe_prologue is a candidate for the next one-dispatch MoE layerlet screen.
