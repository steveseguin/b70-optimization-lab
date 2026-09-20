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

## Update, 2026-09-20: the gate is met, and there is a third literal

Plan step 2 asked for per-card memory in the sampler receipt before choosing
a split. Packets 82 and 83 ship it. From server 83c's
`pipeline-sampler-f83c-tsh-20.json`, during a two-clip stream on the sharded
arm (card total 32.66 GB):

| Card | Allocated | Reserved | Free of reserved |
| --- | --- | --- | --- |
| xpu:0 | 22.34 GB | 28.38 GB | 5.86 GB |
| xpu:1 | 21.02 GB | 28.09 GB | 6.15 GB |
| xpu:2 | 17.74 GB | 23.19 GB | 11.06 GB |
| xpu:3 | 14.95 GB | 17.87 GB | 16.37 GB |

xpu:0 has 5.86 GB free against the 4 GB the plan asked for, and 23/25 moves
1.55 GB onto it, so **step 3's condition is met**. Note the allocator is
holding 6.0 GB of reserved-but-unallocated blocks on xpu:0, so the added
weights may well land inside existing segments without growing reserved at
all.

Plan step 1 is also done, and it changes the value of this lever rather than
unlocking it: the encoder shard is exact but bought nothing
([packet 83](graph-capture-83-results.md)), because the two-clip sampler now
paces the stream at about 1.6 s per clip. So the 23/25 rebalance is no longer
invisible behind the encoder; it is worth its ~0.04 s per clip, about 2.4% of
the current 1.685 s.

### Literal archaeology, corrected

This note said two nodes hard-require 21. The live packet source has
**three**, and the third would have been a serial run-time stop:

| File (packet `source/scripts/`) | Line | Text |
| --- | --- | --- |
| `graph_capture_node.py` | 96 | `require(... == 21, 'Expected the native 21/27 split')` |
| `block_compile_node.py` | 238 | `require(... == 21, 'Expected measured 21/27 split')` |
| `multiblock_compile_node.py` | 353 | same shape, missed by the original survey |

Two call sites choose the split, both passing `split_index=None`, which makes
`ltx_layer_shard.install` compute 21 by byte balance:
`resident_node.py:104` and `host_embedding_resident_node.py:178`. The lane
generator `prepare-multiblock-runtime.py` also carries `'split_index': 21` at
lines 96 and 207 in a packet identity block; that is a different lineage but
must be checked before any packet is regenerated from it.

### Packet 84, ready to build

1. Pass the packet-declared split to both `apply_layer_shard` call sites
   instead of `None`, and relax all three `== 21` requires to that declared
   value rather than deleting them.
2. Declare `split_index: 23` in the packet identity.
3. Run warm plus the thirty-prompt sharded arm against the ten fixture
   oracles. The split changes no arithmetic, so exactness is expected; a
   mismatch would mean the hand-off or a capture signature moved.
4. Read the sampler receipt's memory section again and compare xpu:0
   reserved against the 28.38 GB baseline above.

Do not build this until the host passes a memory test. Two single-byte
corruptions during model load on 2026-09-19/20 mean a 2.4% result from this
machine cannot currently be told apart from noise with confidence.
