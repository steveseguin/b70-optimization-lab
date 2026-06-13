# Qwen3.6 Rank Route Forward Overlay 20260613n

This is a CPU-side diagnostic overlay, not a new speed benchmark.

## Decision

- Decision: `route_distribution_is_rank_invariant`.
- Decode row filter: `num_rows=1`.
- Route-counter identical layers across ranks: `40/40`.
- Hot-expert-counter identical layers across ranks: `0/0` with payload data.
- Hot-expert payload present: `no`.
- Next step: Add layer-family timing around attention, router, expert gather, expert GEMM, combine, and collectives on the slow ranks.

## Per-Rank Overlay

| Rank | Forward end wait ms | Route rows | Unique route hashes/layer | Top16 route coverage | Unique hot experts/layer | Top16 hot coverage | Reversed physical card |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 4.214303 | 25240 | 625.550 | 0.032964 | n/a | n/a | 3 |
| 1 | 4.470655 | 25240 | 625.550 | 0.032964 | n/a | n/a | 2 |
| 2 | 4.769202 | 25240 | 625.550 | 0.032964 | n/a | n/a | 1 |
| 3 | 4.820472 | 25240 | 625.550 | 0.032964 | n/a | n/a | 0 |

## Metric Spreads

| Metric | Min | Max | Spread | Stddev | Pearson vs forward wait |
| --- | ---: | ---: | ---: | ---: | ---: |
| `mean_unique_route_hashes_per_layer` | 625.550000 | 625.550000 | 0.000000 | 0.000000 | null |
| `mean_top1_route_hash_coverage` | 0.004002 | 0.004002 | 0.000000 | 0.000000 | null |
| `mean_top4_route_hash_coverage` | 0.011450 | 0.011450 | 0.000000 | 0.000000 | null |
| `mean_top16_route_hash_coverage` | 0.032964 | 0.032964 | 0.000000 | 0.000000 | null |
| `mean_unique_hot_experts_per_layer` | n/a | n/a | n/a | n/a | null |
| `mean_top16_hot_expert_coverage` | n/a | n/a | n/a | n/a | null |

## Interpretation

- This is a CPU-side overlay of replay-digest route signatures and all-rank forward timing.
- It does not prove kernel causality, but it can reject simple rank route-skew explanations.
- If route and hot-expert counters are rank-invariant, the next probe should split forward time by layer family and collectives rather than generate rank-specific route kernels.
