# Result: A389 - a 512-token prefill batch is 1.7x faster to the first token and changes the output ids

Preregistration: `2026-09-13-a389-32k-prefill-batch-512-prereg.md`. The A381 packet with `PREFILL:512`
(engine kwarg, config assert, identity print and CLI arg all moved from 64); overlay `2a372e86`, served
stage, MAX_MODEL_LEN 33280, KV 1,341,530,112, never-hit + max-count-2 placement, 8 GB host floor, port
20006. Server healthy at 15:45:26 UTC (the VRAM stop rule did not trigger); the same four-depth ladder.

| depth | 512-batch decode tok/s r1 / r2 | 512-batch TTFT s r1 / r2 | 64-batch TTFT s (A381) | ids r1 == r2 | ids == A381 |
|---|---|---|---|---|---|
| 2K | 33.34 / 33.34 | 25.3 (cold) / 6.5 | 29.6 (cold) / 10.9 | yes (`dd0a7f27…`) | **no** (`afffd211…`) |
| 8K | 31.87 / 31.91 | 27.3 | 46.2 | yes (`086e249b…`) | **no** |
| 16K | 32.89 / 32.85 | 55.8 | 96.4 | yes (`9271e8ca…`) | **no** |
| 32K | 32.80 / 32.81 | 114.1 | 199.9 | yes (`a950103a…`) | **no** |

## Reading

- Negative under the lineage's lossless definition: the larger prefill batch changes the output ids at
  every depth (deterministically: both rows agree), because chunked prefill's attention and MoE batch
  shapes change the arithmetic that writes the KV cache. The 64-token batch stays the served identity.
- The prize is real: TTFT falls 1.7x at every depth (32K: 200 -> 114 s; 16K: 96 -> 56 s; 8K: 46 -> 27 s;
  2K warm: 10.9 -> 6.5 s) with decode rates unchanged (31.9-33.3 tok/s). Prefill on this identity is
  launch-bound, not compute-bound, at 64 tokens.
- What it would take: a 512-batch line is a new output authority, i.e. a full certification (quality
  battery, fresh-server repeats, new pins at every depth) rather than a lossless promotion. It is the
  cheapest large TTFT win on the lane and is recorded here as a candidate for a deliberate re-authority
  decision, not preregistered under the lossless campaign.
- Evidence: `experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp0-a389-prefill512-depth-ladder.json`.
