# Laguna — width-two tree: design, and why the verifier is closer than expected

Date: 2026-07-26 America/Toronto

Status: **design only, nothing implemented, nothing measured.** Written while
the host is wedged and no GPU work is possible. Record remains **94.920039**
tok/s.

## Why the tree, not just more depth

Reaching 102 from 94.920039 needs **+7.46%**. The ladder:

| shape | emitted/cycle | vs record | projected tok/s |
| --- | ---: | ---: | ---: |
| depth 7 (record) | 3.703 | — | 94.920 |
| depth 11 (measured) | 3.958 | +6.9% | ~101.5 |
| depth 15 (projected) | ~3.996 | +7.9% | ~102.4 |
| 15-node greedy tree (projected) | ~4.379 | +18.3% | ~112 |

Depth alone is a geometric tail: with per-position acceptance p ≈ 0.756, each
extra node contributes p^d, so depth 12–15 together add only ~0.04 tokens per
cycle. Depth 15 clears 102 by 0.4%, which is not margin — it assumes cycle time
is exactly flat in M, and any 1% cost increase erases it.

The tree attacks the other term. Measured top-k coverage over 2,131 cycles:
**top-1 72.2%, top-2 84.2%**. Conditioned the same way as the chain's p, that
is p₁ ≈ 0.756 and an incremental p₂ ≈ 0.126 for the drafter's second choice.

Expected accepted length for a tree is the sum of path probabilities over all
its nodes, because the target's greedy continuation matches at most one path at
each depth and those events are disjoint. Greedily filling a 15-node budget by
decreasing path probability gives ~3.379 accepted + 1 bonus = **~4.379**.

Note this is why a *full* binary tree is wrong: it needs 2^d nodes at depth d,
so 15 nodes buys only depth 3 (~3.367 emitted) — worse than the depth-7 chain.
The budget must be spent greedily, which puts most nodes on the top-1 spine and
branches only near the root.

## The finding: the metadata layout already admits a tree

`XPUExactSpecDecodeMetadata` carries exactly four fields, and the exact
one-token-per-row rewrite currently builds them as:

```python
q_width   = num_actual_tokens
cu_seqlens_q = arange(q_width + 1)                                  # per-row length-1 queries
seqused_k    = seq_lens[0] - q_width + arange(1, q_width + 1)       # staircase context lengths
block_table  = block_table.expand(q_width, -1).contiguous()         # per-row, currently identical
```

Two of the three tensors are **already per-row and already the right shape** for
a tree:

- `seqused_k` is a per-row context length. A chain needs `base + i + 1`; a tree
  needs `base + depth(i)`. Same tensor, different fill.
- `block_table` is already `(q_width, num_blocks)`. The chain fills every row
  identically; a tree fills each row with its own ancestor blocks.

So the tree does **not** require a new attention kernel, a new metadata
structure, or a tree mask argument. It requires filling two existing tensors
differently. That is a much smaller change than a general tree-attention port.

This also composes with the exact contract rather than fighting it: the rewrite
already re-expresses the verification chunk as q *independent* one-token
sequences, and a tree node is exactly one independent one-token sequence. The
stride-zero BMM that gives each row an independent M=1 GEMM is unchanged.

## The one real obstacle: ancestors are not a prefix

The staircase works because a chain node's ancestors are a **prefix** of the
draft tokens, and `seqused_k` truncation selects exactly a prefix. A tree node's
ancestors are not a prefix — path (1,2,1) skips its siblings — and a block table
selects whole blocks, so siblings sharing a block cannot be masked out. With
`--block-size 64` and ≤15 draft tokens, every draft token for a request lands in
the same block, so truncation cannot separate paths.

Proposed fix: a **per-row scratch block**. Give each of the ≤15 rows one
dedicated block holding, contiguously, the block-aligned tail of the base
context followed by that row's ancestor path. Then:

- `block_table[i] = [shared base blocks ..., scratch_block(i)]`
- `seqused_k[i] = aligned_base_len + tail_len + depth(i)`

Cost is ≤15 blocks of duplicated KV per layer — negligible against a 32 GB card
— plus one scatter to populate them. The base-tail copy is needed because the
context length is arbitrary and the scratch block must begin at a block
boundary.

## Drafter side is nearly free

DFlash is a parallel drafter: all speculative tokens come from **one** masked
forward, and position i is conditioned on the mask tokens, not on the token
chosen at position i−1. The drafter's distribution at position i is therefore
the same regardless of path, so tree branching needs **no** extra drafter
forwards — only a top-2 read from logits it already produces. The exponential
cost of tree drafting lands entirely on the verifier, which is the part the
layout above already accommodates.

## Sequencing

The tree is the lever with margin, but it is unproven and touches the exactness
contract. Width 16 is code-ready today and needs only a GPU. So: measure width
12, then width 16, and only build the tree if width 16 lands short of 102 or
proves fragile. If width 16 does clear 102, the tree becomes the headroom play
rather than the rescue.

Nothing here is measured. Every number in the table above except the first two
rows is a projection from a two-point fit, and the tree row additionally assumes
the measured top-2 coverage transfers to conditional acceptance unchanged.
