# Transformer split rebalance: design and expected value

Written 2026-09-17 while the boot is fault-blocked (offline design only).

## Facts (packet 74b receipts, packet 65 timed forwards)

| Quantity | Value | Source |
| --- | --- | --- |
| Transformer bytes (bf16) | 42.01 GB | `host-components-01-control-result.json` shard report |
| xpu:0 (glue + blocks 0..20) | 21.13 GB | same |
| xpu:1 (blocks 21..47) | 20.88 GB | same |
| Per block | 0.773 GB | 20.88 / 27 |
| Non-block (embeddings, patchify, adaLN, heads) | 4.89 GB | 21.13 - 21 x 0.773 |
| Block time per clip (all 48, graph replay) | 1.57 s | packet 65 `pipe-fwdtimed` |
| Glue time per clip | 0.09 s | same |
| Per-block time | 0.0327 s | 1.57 / 48 |

`ltx_layer_shard.install` picks `split_index` by **byte** balance
(`non_block + 2 * sum(blocks[:n]) ~= sum(blocks)`), which yields 21. Two
nodes hard-require 21 (`graph_capture_node.py:96`, `block_compile_node.py:238`)
and the packet's identity records `split_index: 21`.

## Time balance per clip (two-clip sampler overlaps the cards)

| Split | xpu:0 time | xpu:1 time | Busiest card |
| --- | --- | --- | --- |
| 21/27 (now) | 0.777 s | 0.883 s | 0.883 s |
| 22/26 | 0.809 s | 0.850 s | 0.850 s |
| 23/25 | 0.842 s | 0.817 s | 0.842 s |
| 24/24 | 0.875 s | 0.785 s | 0.875 s |

The two-clip sampler's throughput bound is the busiest card plus the staged
hand-offs, so the best split is **23/25**, worth about 0.04 s per clip
(~5 %) on the sampler bound. 24/24 is worse than 22/26. This lever only
matters once the encoder shard makes the stream sampler-bound; today it is
invisible behind the 1.59 s encoder.

## Memory

23/25 moves 1.55 GB onto xpu:0 (22.7 GB of weights plus activations, graph
pools and the two per-clip stream working sets). No receipt records xpu:0
and xpu:1 during sampling: the graph-capture receipt is taken before the
transformer is resident (xpu:0 shows 0 bytes) and the sampler receipt has no
memory section. Add per-card allocated/reserved to the sampler stream
receipt first; decide the split from that number, not from a guess.

## Plan

1. Packet 76 (encoder shard) first; read the new bound.
2. Add `device_memory()` to the pipeline sampler receipt (source change,
   CPU-testable), ship with the next packet, read xpu:0 headroom after a
   two-clip stream.
3. If headroom >= 4 GB: `split_index=23` via the resident node's shard call,
   relax the two `== 21` requires to the packet-declared value, and run the
   ten-fixture oracle (the split changes no arithmetic; exactness expected).
