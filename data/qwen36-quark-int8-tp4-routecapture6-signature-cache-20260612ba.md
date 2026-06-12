# Qwen3.6 Route Signature Cache Analysis

Inputs: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
Records: `285`
Layers: `3`

## Overall Cache Keys

| key type | available | missing | unique | repeat rate | LRU@4 | LRU@16 | LRU@40 | LRU@64 | LRU@128 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `primitive` | 285 | 0 | 3 | 98.9% | 98.9% | 98.9% | 98.9% | 98.9% | 98.9% |
| `count_vector` | 285 | 0 | 282 | 1.1% | 0.4% | 1.1% | 1.1% | 1.1% | 1.1% |
| `active_set` | 285 | 0 | 282 | 1.1% | 0.4% | 1.1% | 1.1% | 1.1% | 1.1% |
| `topk_tuple` | 285 | 0 | 285 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `count_histogram` | 285 | 0 | 1 | 99.6% | 99.6% | 99.6% | 99.6% | 99.6% | 99.6% |

## Layer Summary

| layer | records | primitive unique | active-set unique | route unique | active repeat | route repeat | route missing | primitive LRU@40 | active LRU@40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `language_model.model.layers.9.mlp.experts` | 95 | 1 | 94 | 95 | 1.1% | 0.0% | 0 | 98.9% | 1.1% |
| `language_model.model.layers.14.mlp.experts` | 95 | 1 | 93 | 95 | 2.1% | 0.0% | 0 | 98.9% | 2.1% |
| `language_model.model.layers.21.mlp.experts` | 95 | 1 | 95 | 95 | 0.0% | 0.0% | 0 | 98.9% | 0.0% |

## Interpretation

- `primitive` approximates a resident oneDNN grouped-matmul key with mutable
  offsets/counts. High LRU hit rates here mean primitive construction can
  move to startup or a small per-layer cache.
- `active_set` and `topk_tuple` approximate route-specialized layerlets.
  Low reuse here means generated kernels should target route classes or
  hot-expert sets, not exact ordered routes.
- Endpoint promotion still requires exact route replay and accepted-service
  provenance; this analysis only decides which cache design is plausible.
