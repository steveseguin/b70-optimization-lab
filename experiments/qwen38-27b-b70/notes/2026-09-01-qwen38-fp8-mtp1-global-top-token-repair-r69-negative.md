# Qwen3.8 FP8 TP2 MTP1 global top-token repair R69: no identity recovery

R69 placed global near-tie detection in the greedy `get_top_tokens` path, but
the strict c1/c2 endpoint screen still reproduced the same `cache-c000` token
96 mismatch in both c2 repeats. The harness failed closed, prompt-cache tokens
were zero, no GPU/Xe fault appeared, and no public result changed.

This excludes the simple R68 path-bypass explanation as a complete cause. A
forced-repair control follows: replay every eligible row rather than relying on
the 0.25 margin. If that passes, candidate detection is wrong; if it fails, an
M=1 target-head replay is insufficient or the active sampling path still does
not consume the repaired token.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-r69-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-global-top-token-repair-r69-result.json).
