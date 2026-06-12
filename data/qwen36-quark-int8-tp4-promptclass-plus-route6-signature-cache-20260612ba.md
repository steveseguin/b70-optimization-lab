# Qwen3.6 Route Signature Cache Analysis

Inputs: `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286309.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286310.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286311.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286312.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-code.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-long-natural.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-natural-chat.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-structured.jsonl, data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
Records: `5485`
Layers: `5`

## Overall Cache Keys

| key type | available | missing | unique | repeat rate | LRU@4 | LRU@16 | LRU@40 | LRU@64 | LRU@128 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `primitive` | 5485 | 0 | 5 | 99.9% | 5.2% | 99.9% | 99.9% | 99.9% | 99.9% |
| `count_vector` | 5485 | 0 | 914 | 83.3% | 0.0% | 1.4% | 1.8% | 1.9% | 2.2% |
| `active_set` | 5485 | 0 | 914 | 83.3% | 0.0% | 1.4% | 1.8% | 1.9% | 2.2% |
| `topk_tuple` | 285 | 5200 | 285 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| `count_histogram` | 5485 | 0 | 1 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

## Layer Summary

| layer | records | primitive unique | active-set unique | route unique | active repeat | route repeat | route missing | primitive LRU@40 | active LRU@40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `language_model.model.layers.8.mlp.experts` | 1040 | 1 | 129 | 0 | 87.6% | 0.0% | 1040 | 99.9% | 2.0% |
| `language_model.model.layers.9.mlp.experts` | 1135 | 1 | 218 | 95 | 80.8% | 0.0% | 1040 | 99.9% | 3.6% |
| `language_model.model.layers.14.mlp.experts` | 1135 | 1 | 217 | 95 | 80.9% | 0.0% | 1040 | 99.9% | 2.5% |
| `language_model.model.layers.20.mlp.experts` | 1040 | 1 | 130 | 0 | 87.5% | 0.0% | 1040 | 99.9% | 1.2% |
| `language_model.model.layers.21.mlp.experts` | 1135 | 1 | 220 | 95 | 80.6% | 0.0% | 1040 | 99.9% | 2.6% |

## Interpretation

- `primitive` approximates a resident oneDNN grouped-matmul key with mutable
  offsets/counts. High LRU hit rates here mean primitive construction can
  move to startup or a small per-layer cache.
- `active_set` and `topk_tuple` approximate route-specialized layerlets.
  Low reuse here means generated kernels should target route classes or
  hot-expert sets, not exact ordered routes.
- Endpoint promotion still requires exact route replay and accepted-service
  provenance; this analysis only decides which cache design is plausible.
