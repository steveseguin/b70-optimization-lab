# Qwen3.6 MoE Flight Record

Inputs: `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-code.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-structured.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-long-natural.jsonl`
Records: `2600`
Window size: `16`

## Ranked Layers

| rank | layer | records | active experts | top16 coverage | top32 coverage | p50 window active | p50 top tuple |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `language_model.model.layers.20.mlp.experts` | 520 | 158 | 0.438 | 0.628 | 24.0 | 0.000 |
| 2 | `language_model.model.layers.14.mlp.experts` | 520 | 155 | 0.423 | 0.616 | 23.0 | 0.000 |
| 3 | `language_model.model.layers.21.mlp.experts` | 520 | 150 | 0.421 | 0.598 | 24.0 | 0.000 |
| 4 | `language_model.model.layers.9.mlp.experts` | 520 | 165 | 0.413 | 0.587 | 22.0 | 0.000 |
| 5 | `language_model.model.layers.8.mlp.experts` | 520 | 163 | 0.401 | 0.578 | 22.0 | 0.000 |

## Interpretation

- Higher hot coverage means hot-expert replication or tile-native repack has more chance to help.
- Lower window active experts means a persistent worker scheduler has less imbalance to solve.
- High top tuple share means repeated exact top-k routes, useful for route-window replay fixtures.
