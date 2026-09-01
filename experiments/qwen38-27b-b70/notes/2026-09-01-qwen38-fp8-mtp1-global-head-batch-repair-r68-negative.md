# Qwen3.8 FP8 TP2 MTP1 global head repair R68: greedy-path bypass

R68 moved the near-tie test across the TP vocabulary boundary, but its strict
c1/c2 endpoint screen still matched only 1/2 c2 outputs. The same `cache-c000`
row diverged at token 96 in both c2 repeats. The harness failed closed, cache
tokens remained zero, no GPU/Xe fault appeared, and no public number changed.

The implementation was attached to `_get_logits`. Greedy serving in this vLLM
build instead takes `LogitsProcessor.get_top_tokens`, an O(batch × TP) local
argmax path that never calls `_get_logits`. R68 therefore did not affect the
endpoint under test. This is a useful negative because it identifies the exact
sampling path rather than weakening the output gate.

R69 applies global top-two detection to `get_top_tokens` itself. It exchanges
two candidate pairs per TP shard and replays only globally ambiguous target
rows at fixed M=1; the draft-only INT4 head remains excluded.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-global-head-batch-repair-r68-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-global-head-batch-repair-r68-result.json).
