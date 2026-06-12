# Qwen3.6 Route-Conditioned Parallelism Simulation

This is a routing proxy, not a kernel benchmark.

Inputs: `data/qwen36-quark-int8-tp4-firstdecode-route-fixture-routes-20260612ct.jsonl`
Matched records: `120`
Windows: `120`

## Policy Summary

| policy | windows | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---:|---:|---:|---:|---:|
| `ep4_contiguous` | 120 | 1.771 | 2.500 | 1.000 | 1.000 |
| `ep4_greedy_static` | 120 | 1.000 | 1.000 | 1.000 | 1.000 |
| `ep4_hot10_replicated_greedy` | 18 | 1.000 | 1.000 | 0.000 | 1.125 |
| `ep4_hot11_replicated_greedy` | 18 | 1.000 | 1.000 | 0.000 | 1.141 |
| `ep4_hot12_replicated_greedy` | 72 | 1.000 | 1.000 | 0.000 | 1.141 |
| `ep4_hot13_replicated_greedy` | 63 | 1.000 | 1.000 | 0.000 | 1.156 |
| `ep4_hot14_replicated_greedy` | 90 | 1.000 | 1.000 | 0.000 | 1.172 |
| `ep4_hot15_replicated_greedy` | 63 | 1.000 | 1.000 | 0.000 | 1.188 |
| `ep4_hot16_replicated_greedy` | 36 | 1.000 | 1.000 | 0.000 | 1.188 |
| `ep4_round_robin` | 120 | 1.892 | 2.500 | 1.000 | 1.000 |
| `tp2_ep2_contiguous` | 120 | 1.288 | 1.750 | 1.000 | 1.000 |
| `tp2_ep2_greedy_static` | 120 | 1.000 | 1.000 | 1.000 | 1.000 |
| `tp2_ep2_round_robin` | 120 | 1.333 | 1.750 | 1.000 | 1.000 |

## Best Policy By Label/Layer

| label | layer | best policy | mean pressure | p95 pressure | mean comm rows | max memory rel |
|---|---|---|---:|---:|---:|---:|
| `firstdecode-route-fixture-routes-20260612ct` | `layers.0.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.1.mlp.experts` | `ep4_hot15_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.10.mlp.experts` | `ep4_hot13_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.156 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.11.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.12.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.13.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.14.mlp.experts` | `ep4_hot15_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.15.mlp.experts` | `ep4_hot15_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.16.mlp.experts` | `ep4_hot13_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.156 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.17.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.18.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.19.mlp.experts` | `ep4_hot13_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.156 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.2.mlp.experts` | `ep4_hot15_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.20.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.21.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.22.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.23.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.24.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.25.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.26.mlp.experts` | `ep4_hot13_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.156 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.27.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.28.mlp.experts` | `ep4_hot10_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.125 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.29.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.3.mlp.experts` | `ep4_hot15_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.30.mlp.experts` | `ep4_hot13_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.156 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.31.mlp.experts` | `ep4_hot11_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.32.mlp.experts` | `ep4_hot11_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.33.mlp.experts` | `ep4_hot13_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.156 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.34.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.35.mlp.experts` | `ep4_hot14_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.172 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.36.mlp.experts` | `ep4_hot13_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.156 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.37.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.38.mlp.experts` | `ep4_hot10_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.125 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.39.mlp.experts` | `ep4_hot12_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.141 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.4.mlp.experts` | `ep4_hot15_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.5.mlp.experts` | `ep4_hot16_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.6.mlp.experts` | `ep4_hot16_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.7.mlp.experts` | `ep4_hot16_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.8.mlp.experts` | `ep4_hot16_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |
| `firstdecode-route-fixture-routes-20260612ct` | `layers.9.mlp.experts` | `ep4_hot15_replicated_greedy` | 1.000 | 1.000 | 0.000 | 1.188 |

## Reading The Numbers

- `compute_pressure_vs_tp4` is normalized so `1.0` means balanced rank work equal to the current TP4 row-work proxy.
- Values above `1.0` are load-imbalance risk. Values below `1.0` are only possible when replication lets hot rows balance better than the TP4 row-work proxy; kernel overhead can still erase that.
- `communication_row_fraction_proxy` is the fraction of routed rows that would still need expert-parallel movement. Plain EP policies are `1.0`; hot-replicated policies reduce this by localizing hot rows.
- `expert_memory_relative_to_tp4` estimates per-rank expert-weight memory relative to current TP4. It ignores dense weights and KV.

