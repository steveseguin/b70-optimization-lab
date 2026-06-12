# Qwen3.6 Route-Conditioned Parallelism Simulation

This is a routing proxy, not a kernel benchmark.

Inputs: `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286309.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286310.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286311.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-1286312.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-code.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-long-natural.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-natural-chat.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-structured.jsonl, data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
Matched records: `5485`
Windows: `325`

## Policy Summary

| policy | windows | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---:|---:|---:|---:|---:|
| `ep4_contiguous` | 325 | 1.279 | 1.469 | 1.000 | 1.000 |
| `ep4_greedy_static` | 325 | 1.213 | 1.406 | 1.000 | 1.000 |
| `ep4_hot16_replicated_greedy` | 325 | 1.022 | 1.062 | 0.549 | 1.188 |
| `ep4_hot32_replicated_greedy` | 325 | 1.001 | 1.000 | 0.356 | 1.375 |
| `ep4_hot64_replicated_greedy` | 325 | 1.000 | 1.000 | 0.155 | 1.750 |
| `ep4_round_robin` | 325 | 1.353 | 1.656 | 1.000 | 1.000 |
| `tp2_ep2_contiguous` | 325 | 1.109 | 1.234 | 1.000 | 1.000 |
| `tp2_ep2_greedy_static` | 325 | 1.079 | 1.172 | 1.000 | 1.000 |
| `tp2_ep2_round_robin` | 325 | 1.150 | 1.312 | 1.000 | 1.000 |

## Best Policy By Label/Layer

| label | layer | best policy | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---|---|---:|---:|---:|---:|
| `1286309` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.193 | 1.750 |
| `1286309` | `layers.20.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.170 | 1.750 |
| `1286309` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.213 | 1.750 |
| `1286309` | `layers.8.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.215 | 1.750 |
| `1286309` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.210 | 1.750 |
| `1286310` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.193 | 1.750 |
| `1286310` | `layers.20.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.170 | 1.750 |
| `1286310` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.213 | 1.750 |
| `1286310` | `layers.8.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.215 | 1.750 |
| `1286310` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.210 | 1.750 |
| `1286311` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.193 | 1.750 |
| `1286311` | `layers.20.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.170 | 1.750 |
| `1286311` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.213 | 1.750 |
| `1286311` | `layers.8.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.215 | 1.750 |
| `1286311` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.210 | 1.750 |
| `1286312` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.193 | 1.750 |
| `1286312` | `layers.20.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.170 | 1.750 |
| `1286312` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.213 | 1.750 |
| `1286312` | `layers.8.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.215 | 1.750 |
| `1286312` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.210 | 1.750 |
| `6-routes-rank0-20260611` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.128 | 1.750 |
| `6-routes-rank0-20260611` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.141 | 1.750 |
| `6-routes-rank0-20260611` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.084 | 1.750 |
| `math-reasoning` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.047 | 1.750 |
| `math-reasoning` | `layers.20.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.085 | 1.750 |
| `math-reasoning` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.077 | 1.750 |
| `math-reasoning` | `layers.8.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.083 | 1.750 |
| `math-reasoning` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.111 | 1.750 |
| `repetitive` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.172 | 1.750 |
| `repetitive` | `layers.20.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.113 | 1.750 |
| `repetitive` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.139 | 1.750 |
| `repetitive` | `layers.8.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.141 | 1.750 |
| `repetitive` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.128 | 1.750 |

## Reading The Numbers

- `compute_pressure_vs_tp4` is normalized so `1.0` means balanced rank work equal to the current TP4 row-work proxy.
- Values above `1.0` are load-imbalance risk. Values below `1.0` are only possible when replication lets hot rows balance better than the TP4 row-work proxy; kernel overhead can still erase that.
- `communication_row_fraction_proxy` is the fraction of routed rows that would still need expert-parallel movement. Plain EP policies are `1.0`; hot-replicated policies reduce this by localizing hot rows.
- `expert_memory_relative_to_tp4` estimates per-rank expert-weight memory relative to current TP4. It ignores dense weights and KV.
