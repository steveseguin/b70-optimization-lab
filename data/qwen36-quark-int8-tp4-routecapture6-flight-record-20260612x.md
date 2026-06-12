# Qwen3.6 MoE Flight Record

Inputs: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
Records: `285`
Window size: `16`

## Ranked Layers

| rank | layer | records | active experts | top16 coverage | top32 coverage | p50 window active | p50 top tuple |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `language_model.model.layers.9.mlp.experts` | 95 | 111 | 0.511 | 0.722 | 47.0 | 0.062 |
| 2 | `language_model.model.layers.21.mlp.experts` | 95 | 119 | 0.489 | 0.683 | 48.5 | 0.062 |
| 3 | `language_model.model.layers.14.mlp.experts` | 95 | 126 | 0.421 | 0.645 | 50.0 | 0.062 |

## Interpretation

- Higher hot coverage means hot-expert replication or tile-native repack has more chance to help.
- Lower window active experts means a persistent worker scheduler has less imbalance to solve.
- High top tuple share means repeated exact top-k routes, useful for route-window replay fixtures.
