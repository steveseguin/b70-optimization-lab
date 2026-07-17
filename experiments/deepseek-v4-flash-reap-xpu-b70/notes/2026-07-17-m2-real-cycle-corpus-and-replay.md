# M=2 real-cycle corpus and fixed-buffer replay worker

Date: 2026-07-17

## Outcome

The first fixed-geometry decoder-shell artifact is operational. One eager
diagnostic load of the exact 63.851301 tok/s record identity captured the real
M=2 TP4/MHC cycle into a 150 MiB content-addressed corpus. A standalone
four-B70 worker then loaded that corpus without the 96 GiB model and replayed
the complete 87-reduction/85-consumer graph bitwise exactly **70/70** times.
The slowest-rank median over 20 timed replays is `4.209382 ms/cycle`.

This is not a decode-speed or LocalMax result. It is the reusable, exact
baseline for developing communication and consumer kernels in seconds rather
than reloading the full model for every candidate.

## Corpus identity

- capture vLLM: `9fc754a` on exact record parent `4a6fd8747`;
- XPU kernels: record `18a44f440`;
- model: unchanged frozen uniform-K160 artifact;
- prompt cache: zero cached tokens;
- corpus:
  `/mnt/fast-ai/deepseek-v4-corpora/mtp1-m2-cycle-20260717T0710Z`;
- aggregate manifest SHA-256:
  `1015e86b1cf46476dbbd10d1cf0cec92246b8af406149f17b0f2dd62b6dd37cd`.

Each of four ranks has:

- 87 rank-local and reduced BF16 `[2,4096]` TP tensors;
- 85 boundary-ordered native M=2 MHC input/output records;
- 85/85 MHC reduced inputs linked by raw hash to the corresponding collective;
- the exact layer order: layer-0 FFN, then attention/FFN for layers 1-42;
- 84 successive residual storage aliases recorded for layout/lifetime parity.

All 87 reduced tensors agree across ranks. The complete corpus contains 688
small record manifests and 1,030 unique tensor blobs. Content addressing
deduplicates replicated weights, reduced tensors, and states; logical tensor
payload is 147,823,004 bytes and on-disk use is about 150 MiB.

## Replay worker

`scripts/replay-m2-cycle-corpus.py` loads rank-specific local partials and
boundary tensors, allocates immutable fixed addresses, and captures this graph:

```text
87 real local-partial copies -> 87 TP4 sums
  -> 85 native M=2 MHC post/pre consumers
  -> one BF16 completion witness after every consumer
```

It compares every reduced element and all four MHC outputs after every replay.
The first promoted baseline passes 70/70 fixed-address replays and measures
`4.209382 ms` at the slowest rank. Raw evidence is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m2-real-cycle-replay-20260717T0720Z`.

## Why this matters

The prior finite event-chain experiment needed a full-model interpretation to
discover that its eager gain disappeared under graph replay. This worker makes
the production-relevant graph comparator the default. A new bridge, fused
consumer, command-list policy, or transport can now be rejected or promoted
against real tensors before model load. It also preserves real storage-alias
metadata required by earlier collective/MHC correctness failures.

Next, extend this shell only with candidates that delete device or collective
work. In parallel, use the same content-addressed format for exact M=4/M=8
verifier economics and held-out deeper-speculation evaluation.
