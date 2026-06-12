# Qwen3.6 Route-Conditioned Parallelism Simulation

This is a routing proxy, not a kernel benchmark.

Inputs: `data/qwen36-quark-int8-tp4-routecapture6-routes-rank0-20260611.jsonl`
Matched records: `285`
Windows: `15`

## Policy Summary

| policy | windows | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---:|---:|---:|---:|---:|
| `ep4_contiguous` | 15 | 1.304 | 1.497 | 1.000 | 1.000 |
| `ep4_greedy_static` | 15 | 1.238 | 1.456 | 1.000 | 1.000 |
| `ep4_hot16_replicated_greedy` | 15 | 1.015 | 1.031 | 0.529 | 1.188 |
| `ep4_hot32_replicated_greedy` | 15 | 1.002 | 1.009 | 0.311 | 1.375 |
| `ep4_hot64_replicated_greedy` | 15 | 1.000 | 1.000 | 0.118 | 1.750 |
| `ep4_round_robin` | 15 | 1.425 | 1.659 | 1.000 | 1.000 |
| `tp2_ep2_contiguous` | 15 | 1.111 | 1.217 | 1.000 | 1.000 |
| `tp2_ep2_greedy_static` | 15 | 1.079 | 1.177 | 1.000 | 1.000 |
| `tp2_ep2_round_robin` | 15 | 1.176 | 1.356 | 1.000 | 1.000 |

## Best Policy By Label/Layer

| label | layer | best policy | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---|---|---:|---:|---:|---:|
| `6-routes-rank0-20260611` | `layers.14.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.128 | 1.750 |
| `6-routes-rank0-20260611` | `layers.21.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.141 | 1.750 |
| `6-routes-rank0-20260611` | `layers.9.mlp.experts` | `ep4_hot64_replicated_greedy` | 1.000 | 1.000 | 0.084 | 1.750 |

## Reading The Numbers

- `compute_pressure_vs_tp4` is normalized so `1.0` means balanced rank work equal to the current TP4 row-work proxy.
- Values above `1.0` are load-imbalance risk. Values below `1.0` are only possible when replication lets hot rows balance better than the TP4 row-work proxy; kernel overhead can still erase that.
- `communication_row_fraction_proxy` is the fraction of routed rows that would still need expert-parallel movement. Plain EP policies are `1.0`; hot-replicated policies reduce this by localizing hot rows.
- `expert_memory_relative_to_tp4` estimates per-rank expert-weight memory relative to current TP4. It ignores dense weights and KV.

