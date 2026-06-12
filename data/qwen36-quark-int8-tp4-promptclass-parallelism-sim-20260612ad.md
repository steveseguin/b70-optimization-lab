# Qwen3.6 Route-Conditioned Parallelism Simulation

This is a routing proxy, not a kernel benchmark.

Inputs: `data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-code.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-math-reasoning.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-repetitive.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-structured.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-long-natural.jsonl, data/qwen36-quark-int8-tp4-promptclass-routecapture-20260611a-routes-natural-chat.jsonl`
Matched records: `2600`
Windows: `150`

## Policy Summary

| policy | windows | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---:|---:|---:|---:|---:|
| `ep4_contiguous` | 150 | 1.276 | 1.469 | 1.000 | 1.000 |
| `ep4_greedy_static` | 150 | 1.193 | 1.312 | 1.000 | 1.000 |
| `ep4_hot16_replicated_greedy` | 150 | 1.015 | 1.031 | 0.515 | 1.188 |
| `ep4_hot32_replicated_greedy` | 150 | 1.001 | 1.000 | 0.313 | 1.375 |
| `ep4_hot64_replicated_greedy` | 150 | 1.000 | 1.000 | 0.109 | 1.750 |
| `ep4_round_robin` | 150 | 1.346 | 1.688 | 1.000 | 1.000 |
| `tp2_ep2_contiguous` | 150 | 1.107 | 1.243 | 1.000 | 1.000 |
| `tp2_ep2_greedy_static` | 150 | 1.069 | 1.156 | 1.000 | 1.000 |
| `tp2_ep2_round_robin` | 150 | 1.151 | 1.297 | 1.000 | 1.000 |

## Best Policy By Label/Layer

| label | layer | best policy | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---|---|---:|---:|---:|---:|
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

