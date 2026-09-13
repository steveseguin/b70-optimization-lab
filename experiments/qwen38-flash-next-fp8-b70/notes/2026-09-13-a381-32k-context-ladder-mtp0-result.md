# Result: A381 - the promoted MTP0 line at a 33,280-token capacity, 2K to 32K input

Preregistration: `2026-09-13-a375-a376-32k-context-ladder-prereg.md` (A375 re-run as A381 after the
supervisor-floor and launcher-assertion fixes, amendments 1-2). Overlay `2a372e86`, served stage, W13-N64
map, never-hit + max-count-2 placement, `MAX_MODEL_LEN=33280`, KV 1,341,530,112 bytes (90,965 tokens),
port 19994. Server healthy at 09:24:53 UTC; host MemAvailable trough 9.16 GB (floor 8 GB), steady 9.7 GB.
Depth harness `scripts/bench-openai-token-depth-suite.py` on the lane's exact-depth fixture, two rows per
depth, 99-interval decode rate after the first token.

| depth | decode tok/s r1 / r2 | TTFT s r1 / r2 | output ids sha256 | r1 == r2 |
|---|---|---|---|---|
| 2K | 33.39 / 33.24 | 29.6 / 10.9 | `afffd211…` | yes |
| 8K | 32.02 / 32.08 | 46.2 / 46.2 | `0126d542…` | yes |
| 16K | 31.37 / 31.33 | 96.4 / 96.3 | `789cbcb8…` | yes |
| 32K | 32.67 / 32.66 | 199.9 / 199.9 | `1cc1699e…` | yes |

## Reading

- Lossless within the line at every depth: both rows agree at 2K, 8K, 16K and 32K, and the 2K rows
  reproduce the certified pin `afffd211…` (the MTP0 and MTP1 lines share it), on a server whose capacity,
  KV budget and expert placement all differ from the certified packet. The 8K/16K/32K hashes are the
  first recorded for this lineage and become the pins for the MTP1 arm (A382), whose gate is equality
  with these.
- Decode rate is flat with depth: 32K keeps 98% of the 2K rate (32.7 vs 33.4 tok/s); the sparse
  attention and fixed-size GDN state bound the attention cost as predicted. The 2K rate matches the
  certified MTP0 line (33.8) within run-to-run noise, so the wider placement costs nothing measurable.
- TTFT grows linearly with depth at ~6 s per 1K tokens (prefill runs in 64-token batches on this
  identity: 200 s at 32K). A long-context product cell needs a larger prefill batch, a separate lever
  with its own identity gate.
- Publication: the "32K input" cell can be filled for the MTP0 line from this arm alone (MTP0-only, as
  the preregistration allows); the exact-mode MTP1 line's cell waits for A382.
