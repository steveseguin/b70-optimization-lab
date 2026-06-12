# Qwen3.6 MoE Flight Record

Inputs: `data/qwen36-quark-int8-tp4-routecapture5-routes-rank0-20260611.jsonl`
Records: `254`
Window size: `16`

## Ranked Layers

| rank | layer | records | active experts | top16 coverage | top32 coverage | p50 window active | p50 top tuple |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `language_model.model.layers.8.mlp.experts` | 127 | 117 | 0.548 | 0.755 | 44.0 | 0.062 |
| 2 | `language_model.model.layers.20.mlp.experts` | 127 | 125 | 0.534 | 0.729 | 46.0 | 0.062 |

## Interpretation

- Higher hot coverage means hot-expert replication or tile-native repack has more chance to help.
- Lower window active experts means a persistent worker scheduler has less imbalance to solve.
- High top tuple share means repeated exact top-k routes, useful for route-window replay fixtures.
